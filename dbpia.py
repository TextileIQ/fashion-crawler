#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 필요한 라이브러리들을 가져옵니다 (import = 가져오기)
from selenium import webdriver  # 웹 브라우저를 자동으로 조작하는 도구
from selenium.webdriver.chrome.service import Service  # 크롬 브라우저 서비스
from selenium.webdriver.chrome.options import Options  # 크롬 브라우저 옵션 설정
from selenium.webdriver.common.by import By  # 웹페이지에서 요소를 찾는 방법들
from webdriver_manager.chrome import ChromeDriverManager  # 크롬 드라이버 자동 설치
import time  # 시간 관련 기능 (대기시간 등)
import csv  # CSV 파일 처리
import pandas as pd  # 데이터 처리 및 엑셀 파일 생성
from datetime import datetime  # 현재 날짜/시간 가져오기
import os  # 파일 시스템 관련 기능
import logging  # 로그(기록) 관리
import json  # JSON 데이터 처리
import threading  # 멀티스레딩
from concurrent.futures import ThreadPoolExecutor  # 스레드 풀
import queue  # 스레드 간 데이터 전달

def process_single_paper(link_data, thread_id, results_queue, filename):
    """단일 논문 처리 함수 (병렬 처리용)"""
    link, idx = link_data
    
    # 각 스레드마다 독립적인 브라우저 인스턴스 생성
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    service.log_path = os.devnull
    browser = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        print(f"🔄 스레드 {thread_id}: 논문 {idx} 처리 중...")
        browser.get(link)
        time.sleep(2)
        
        # JSON-LD 데이터에서 정보 추출
        json_ld_data = None
        try:
            json_ld_script = browser.find_element(By.XPATH, "//script[@type='application/ld+json']")
            json_ld_data = json.loads(json_ld_script.get_attribute('innerHTML'))
        except:
            pass
        
        # 논문 제목
        title = "제목 없음"
        if json_ld_data and 'headline' in json_ld_data:
            title = json_ld_data['headline']
        else:
            try:
                title = browser.find_element(By.CLASS_NAME, 'thesis__title').text.strip()
            except:
                pass
        
        # 논문 저자
        author = "저자 없음"
        if json_ld_data and 'author' in json_ld_data:
            if isinstance(json_ld_data['author'], list):
                author = ', '.join([author_item.get('name', '') if isinstance(author_item, dict) else str(author_item) for author_item in json_ld_data['author']])
            elif isinstance(json_ld_data['author'], dict):
                author = json_ld_data['author'].get('name', '')
            else:
                author = str(json_ld_data['author'])
        else:
            try:
                author = browser.find_element(By.CLASS_NAME, 'thesis__author').text.strip()
            except:
                pass
        
        # 논문 초록
        abstract = "초록 없음"
        try:
            abstract = browser.find_element(By.CLASS_NAME, 'abstractTxt').text.strip()
        except:
            pass
        
        # 발행년도
        year = "년도 없음"
        if json_ld_data and 'datePublished' in json_ld_data:
            year = json_ld_data['datePublished'][:4]
        else:
            try:
                year_element = browser.find_element(By.CLASS_NAME, 'thesis__year')
                year = year_element.text.strip()
            except:
                pass
        
        # 학술지명
        journal = "학술지 없음"
        if json_ld_data and 'isPartOf' in json_ld_data:
            if isinstance(json_ld_data['isPartOf'], dict):
                journal = json_ld_data['isPartOf'].get('name', '')
            else:
                journal = str(json_ld_data['isPartOf'])
        else:
            try:
                journal = browser.find_element(By.CLASS_NAME, 'thesis__journal').text.strip()
            except:
                pass
        
        # 수록면 정보
        page_info = "수록면 정보 없음"
        if json_ld_data and 'pagination' in json_ld_data:
            if isinstance(json_ld_data['pagination'], dict):
                page_start = json_ld_data['pagination'].get('pageStart', '')
                page_end = json_ld_data['pagination'].get('pageEnd', '')
                if page_start:
                    page_info = page_start
                    if page_end:
                        page_info += f"-{page_end}"
            else:
                page_info = str(json_ld_data['pagination'])
        else:
            try:
                page_selectors = ['thesis__page', 'thesis__pages', 'page-info', 'thesis__volume', 'thesis__issue']
                for selector in page_selectors:
                    try:
                        page_element = browser.find_element(By.CLASS_NAME, selector)
                        page_info = page_element.text.strip()
                        if page_info:
                            break
                    except:
                        continue
            except:
                pass
        
        # 데이터 정리
        paper_info = {
            '번호': idx,
            '제목': title,
            '저자': author,
            '학술지': journal,
            '발행년도': year,
            '수록면': page_info,
            '초록': abstract,
            '링크': link,
            '크롤링날짜': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 결과를 큐에 전달
        results_queue.put(paper_info)
        print(f"✅ 스레드 {thread_id}: {title[:30]}... 완료!")
        
    except Exception as e:
        print(f"❌ 스레드 {thread_id}: 논문 {idx} 처리 실패: {e}")
        # 오류 발생 시 기본 정보 저장
        paper_info = {
            '번호': idx,
            '제목': '처리 실패',
            '저자': '처리 실패',
            '학술지': '처리 실패',
            '발행년도': '처리 실패',
            '수록면': '처리 실패',
            '초록': '처리 실패',
            '링크': link,
            '크롤링날짜': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        results_queue.put(paper_info)
        
    finally:
        browser.quit()

def crawl_dbpia_papers():
    """DBPIA 논문 크롤링 메인 함수"""
    
    # 경고 메시지 숨기기
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # 브라우저 시작
    print("🌐 브라우저를 시작하는 중...")
    
    # Chrome 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 브라우저 실행
    service = Service(ChromeDriverManager().install())
    service.log_path = os.devnull
    browser = webdriver.Chrome(service=service, options=chrome_options)
    browser.maximize_window()
    
    try:
        # 검색어 입력
        search_word = input("🔍 검색하시고자 하는 논문 제목을 입력하세요: ")
        
        # URL 생성
        url = 'https://www.dbpia.co.kr/search/topSearch?startCount=0&collection=ALL&range=A&searchField=ALL&sort=RANK&query={}&srchOption=*&includeAr=false'
        final_url = url.format(search_word)
        
        print(f"🔗 검색 URL: {final_url}")
        browser.get(final_url)
        browser.implicitly_wait(10)
        time.sleep(5)
        
        # 페이지 로딩 확인
        print("📄 페이지 로딩 완료 확인 중...")
        print(f"📋 현재 페이지 제목: {browser.title}")
        
        # 검색 결과 확인
        try:
            result_elements = browser.find_elements(By.CLASS_NAME, 'thesis__pageLink')
            print(f"📊 찾은 논문 링크 수: {len(result_elements)}")
            
            if len(result_elements) == 0:
                print("⚠️ 검색 결과가 없습니다. 다른 검색어를 시도해보세요.")
                page_source = browser.page_source
                if "검색결과가 없습니다" in page_source or "no results" in page_source.lower():
                    print("✅ 확인: 검색 결과가 없다는 메시지 발견")
                else:
                    print("🔍 페이지에 다른 요소들이 있는지 확인 중...")
                    alternative_elements = browser.find_elements(By.CSS_SELECTOR, 'a[href*="thesis"]')
                    print(f"🔄 대안 요소 수: {len(alternative_elements)}")
        except Exception as e:
            print(f"❌ 검색 결과 확인 중 오류: {e}")
        
        # 데이터 저장용 리스트
        paper_data = []
        link_list = []
        processed_titles = set()  # 중복 제목 체크용
        
        # CSV 파일명 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'dbpia_papers_{search_word}_{timestamp}.csv'
        
        # 첫 번째 페이지 링크 수집
        print("📄 첫 번째 페이지 링크 수집 중...")
        links = browser.find_elements(By.CLASS_NAME, 'thesis__pageLink')
        print(f"🔗 첫 페이지에서 찾은 링크 수: {len(links)}")
        
        # 대안 선택자 시도
        if len(links) == 0:
            print("🤔 기본 선택자로 링크를 찾지 못했습니다. 다른 방법들을 시도해볼게요...")
            alternative_selectors = [
                'a[href*="thesis"]',
                '.thesis a',
                '.search-result a',
                '.paper-item a',
                'a[href*="dbpia"]'
            ]
            
            for selector in alternative_selectors:
                try:
                    alt_links = browser.find_elements(By.CSS_SELECTOR, selector)
                    print(f"🔍 선택자 '{selector}'로 찾은 링크 수: {len(alt_links)}")
                    if len(alt_links) > 0:
                        links = alt_links
                        break
                except Exception as e:
                    print(f"❌ 선택자 '{selector}' 시도 중 오류: {e}")
        
        # 링크 저장 (중복 제거)
        for link in links:
            href = link.get_attribute('href')
            if href and href not in link_list:
                link_list.append(href)
                print(f"✅ 링크 추가: {href[:50]}...")
            elif href in link_list:
                print(f"⚠️ 중복 링크 제외: {href[:50]}...")
        
        # 모든 페이지 링크 수집 (무한 반복!)
        page_num = 2
        while True:  # 무한 반복!
            try:
                print(f"📄 {page_num}페이지 링크 수집 중...")
                xpath = f'//*[@id="pageList"]/a[{page_num}]'
                page_button = browser.find_element(By.XPATH, xpath)
                browser.execute_script("arguments[0].click();", page_button)
                time.sleep(3)
                
                # 현재 페이지의 링크 수집
                links = browser.find_elements(By.CLASS_NAME, 'thesis__pageLink')
                new_links_count = 0
                
                for link in links:
                    href = link.get_attribute('href')
                    if href and href not in link_list:
                        link_list.append(href)
                        new_links_count += 1
                
                # 새로운 링크가 없으면 더 이상 페이지가 없다는 뜻!
                if new_links_count == 0:
                    print(f"✅ {page_num}페이지에 새로운 논문이 없습니다. 크롤링 완료!")
                    break
                
                print(f"✅ {page_num}페이지에서 {new_links_count}개 새 링크 발견!")
                page_num += 1  # 다음 페이지로
                        
            except Exception as e:
                print(f"❌ {page_num}페이지 처리 중 오류: {e}")
                print("🗯️ 더 이상 페이지가 없습니다. 크롤링 완료!")
                break  # 오류가 발생하면 반복 종료
        
        print(f"🍀 총 {len(link_list)}개 논문 링크 수집 완료!")
        
        # 링크가 없으면 종료
        if len(link_list) == 0:
            print("❌ 수집된 논문 링크가 없습니다. 검색어를 변경하거나 사이트 구조를 확인해주세요.")
            return None, []
        
        # 병렬 처리로 논문 상세 정보 수집! 🚀
        print(f"🚀 병렬 처리 시작! (최대 4개 스레드)")
        
        # 스레드 풀 생성 (최대 4개 스레드)
        max_workers = min(4, len(link_list))  # 논문 수가 적으면 스레드 수도 조정
        results_queue = queue.Queue()
        
        # 링크 데이터 준비
        link_data_list = [(link, idx) for idx, link in enumerate(link_list, 1)]
        
        # ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 모든 작업 제출
            futures = []
            for i, link_data in enumerate(link_data_list):
                future = executor.submit(process_single_paper, link_data, i+1, results_queue, filename)
                futures.append(future)
            
            # 결과 수집 (실시간)
            completed_count = 0
            while completed_count < len(link_list):
                try:
                    # 큐에서 결과 가져오기 (타임아웃 1초)
                    paper_info = results_queue.get(timeout=1)
                    paper_data.append(paper_info)
                    completed_count += 1
                    
                    # 실시간 CSV 저장
                    df = pd.DataFrame(paper_data)
                    df.to_csv(filename, index=False, encoding='utf-8-sig')
                    
                    print(f"😺 진행률: {completed_count}/{len(link_list)} ({completed_count/len(link_list)*100:.1f}%)")
                    
                except queue.Empty:
                    # 타임아웃 발생 시 계속 대기
                    continue
            
            # 모든 작업 완료 대기
            for future in futures:
                future.result()
        
        # 크롤링 완료 결과 출력
        print(f"\n🎉 === 크롤링 완료! ===")
        print(f"📁 파일명: {filename}")
        print(f"😺 총 논문 수: {len(paper_data)}")
        print(f"💾 저장 위치: {os.path.abspath(filename)}")
        
        # 수집된 논문 목록 미리보기
        print("\n📋 === 수집된 논문 목록 ===")
        for i, paper in enumerate(paper_data[:5], 1):
            print(f"{i}. {paper['제목']}")
            print(f"   👤 저자: {paper['저자']}")
            print(f"   📚 학술지: {paper['학술지']}")
            print(f"   📄 수록면: {paper['수록면']}")
            print()
        
        if len(paper_data) > 5:
            print(f"... 외 {len(paper_data)-5}개 논문")
        
        return filename, paper_data
        
    except Exception as e:
        error_message = f"❌ 크롤링 중 오류 발생: {e}"
        print(error_message)
        return None, []
        
    finally:
        print("🌐 브라우저를 종료합니다...")
        browser.quit()

def main():
    print("=" * 50)
    print("🎓 DBPIA 논문 크롤링 프로그램")
    print("=" * 50)
    
    filename, data = crawl_dbpia_papers()
    
    if filename:
        print(f"\n🎉 ✅ 성공적으로 완료되었습니다!")
        print(f"😎 파일 확인: {filename}")
    else:
        print("\n❌ 크롤링에 실패했습니다.")

if __name__ == "__main__":
    main()