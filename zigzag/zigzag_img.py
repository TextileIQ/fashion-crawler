import os
import json
import asyncio
import re
from urllib.parse import unquote
from pathlib import Path
from playwright.async_api import async_playwright
import aiohttp
import aiofiles

# 환경 설정 (envConfig 대신)
class EnvConfig:
    SCROLL_ITERATIONS = 10
    SCROLL_DELAY_MS = 1000
    JSON_INDENT = 2
    IMAGE_LIMIT = 50

env_config = EnvConfig()

REVIEW_IMAGE_SELECTOR = "div.css-s01evr.efs1gt61 img"
REVIEW_TEXT_SELECTOR = "div.css-s01evr.efs1gt61"

async def extract_title_from_zigzag(page, product_page_url):
    """지그재그 상품 페이지에서 제목을 추출"""
    await page.goto(product_page_url, wait_until='networkidle')
    
    title = await page.evaluate('''() => {
        const titleEl = document.querySelector("h1.BODY_15.REGULAR");
        return titleEl ? titleEl.innerText.trim() : null;
    }''')
    
    return title or "상품명 없음"

async def resolve_redirect_and_extract_product_info(page, input_url):
    """리디렉션을 처리하고 상품 정보를 추출"""
    final_url = input_url
    
    if "s.zigzag.kr" in input_url or "zigzag.kr/p/" in input_url:
        await page.goto(input_url, wait_until='networkidle')
        final_url = page.url
        print(f"리디렉션 완료: {final_url}")
        
        # deeplink_url 파라미터에서 실제 URL 추출
        deeplink_match = re.search(r'deeplink_url=([^&]+)', final_url)
        if deeplink_match:
            final_url = unquote(deeplink_match.group(1))
    
    # 상품 ID 추출
    match = re.search(r'products/(\d+)', final_url)
    if not match:
        raise Exception("상품 ID를 추출할 수 없습니다.")
    
    product_id = match.group(1)
    review_url = f"https://zigzag.kr/review/list/{product_id}"
    product_page_url = f"https://zigzag.kr/catalog/products/{product_id}"
    
    return {
        'product_id': product_id,
        'review_url': review_url,
        'product_page_url': product_page_url
    }

async def scroll_to_load_all_reviews(page):
    """모든 후기를 로드하기 위해 스크롤"""
    for i in range(env_config.SCROLL_ITERATIONS):
        await page.evaluate('() => window.scrollBy(0, window.innerHeight)')
        await asyncio.sleep(env_config.SCROLL_DELAY_MS / 1000)  # ms를 초로 변환

async def extract_review_image_urls(page):
    """후기 이미지 URL들을 추출"""
    return await page.evaluate(f'''(selector) => {{
        const urls = new Set();
        const images = document.querySelectorAll(selector);
        
        images.forEach((img) => {{
            const src = img.getAttribute("src") || "";
            
            if (src.includes("zigzag.kr/original/review/")) {{
                urls.add(src.split("?")[0]);
            }}
        }});
        
        return Array.from(urls);
    }}''', REVIEW_IMAGE_SELECTOR)

async def save_image_urls_to_json(file_path, urls):
    """이미지 URL들을 JSON 파일로 저장"""
    # 디렉터리 생성
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    
    # JSON 파일로 저장
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(urls, indent=env_config.JSON_INDENT, ensure_ascii=False))
    
    print(f"후기 이미지 URL {len(urls)}개 JSON 저장 완료")

async def download_images(product_id, image_urls):
    """이미지들을 다운로드 (실제 구현은 별도 함수로)"""
    # 이 함수는 원본의 downloadImages 함수를 구현해야 합니다
    print(f"이미지 다운로드 시작: {len(image_urls)}개 (상품 ID: {product_id})")
    
    # 실제 다운로드 로직을 여기에 구현
    download_dir = Path(f"downloads/{product_id}")
    download_dir.mkdir(parents=True, exist_ok=True)
    
    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(image_urls):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        filename = f"review_image_{i+1}.jpg"
                        file_path = download_dir / filename
                        
                        async with aiofiles.open(file_path, 'wb') as f:
                            await f.write(await response.read())
                        
                        print(f"다운로드 완료: {filename}")
            except Exception as e:
                print(f"이미지 다운로드 실패 ({url}): {e}")

def guess_category_from_title(title):
    """제목에서 카테고리를 추측 (실제 구현은 별도 함수로)"""
    # 원본의 guessCategoryFromTitle 함수를 구현해야 합니다
    # 간단한 예시 구현
    title_lower = title.lower()
    
    if any(word in title_lower for word in ['셔츠', '블라우스', 'shirt']):
        return '의류-상의'
    elif any(word in title_lower for word in ['바지', '팬츠', 'pants']):
        return '의류-하의'
    elif any(word in title_lower for word in ['신발', 'shoes']):
        return '신발'
    elif any(word in title_lower for word in ['가방', 'bag']):
        return '가방'
    else:
        return '기타'

async def crawl_zigzag_review_images(product_url, output_path="data/review-images.json"):
    """지그재그 후기 이미지를 크롤링하는 메인 함수"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # 상품 정보 추출
            product_info = await resolve_redirect_and_extract_product_info(page, product_url)
            product_id = product_info['product_id']
            review_url = product_info['review_url']
            product_page_url = product_info['product_page_url']
            
            # 후기 페이지로 이동 및 스크롤
            await page.goto(review_url, wait_until='networkidle')
            await scroll_to_load_all_reviews(page)
            
            # 이미지 URL 추출
            image_urls = await extract_review_image_urls(page)
            limited = image_urls[:env_config.IMAGE_LIMIT]
            
            if not limited:
                raise Exception("🥲 후기 이미지가 존재하지 않습니다")
            
            # JSON 저장 및 이미지 다운로드
            await save_image_urls_to_json(output_path, limited)
            await download_images(product_id, limited)
            
            print(f"🖼️ 지그재그 후기 이미지 {len(limited)}장 크롤링 완료 ({product_id})")
            
            # 제목 및 카테고리 추출
            title = await extract_title_from_zigzag(page, product_page_url)
            category = guess_category_from_title(title)
            
            return {
                'success': True,
                'product_id': product_id,
                'category': category,
                'imageCount': len(limited),
                'images': limited
            }
            
        except Exception as err:
            print(f"🥲 지그재그 크롤링 실패: {err}")
            raise err
        finally:
            await browser.close()

# 추가 유틸리티 함수들

def is_match_site(url, keywords=None):
    """사이트 매칭 확인"""
    if keywords is None:
        keywords = []
    return any(keyword in url for keyword in keywords)

async def send_images_to_server(product_id, source, image_urls, server_api_url):
    """서버로 이미지 정보 전송"""
    try:
        data = {
            "product_id": product_id,
            "source": source,
            "image_urls": image_urls
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(server_api_url, json=data) as response:
                if response.status == 200:
                    print("서버 전송 성공")
                    return await response.json()
                else:
                    raise Exception(f"HTTP {response.status}")
                    
    except Exception as error:
        print(f"서버 전송 실패: {error}")
        raise error
async def main():
    """메인 실행 함수"""
    try:
        # 실제 지그재그 상품 URL로 테스트
        product_url = "https://zigzag.kr/catalog/products/150012796"  # 실제 상품 ID 사용
        result = await crawl_zigzag_review_images(product_url)
        print("크롤링 결과:", result)
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())