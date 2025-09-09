import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

async def complete_crawl(product_url):
    """리뷰 텍스트 크롤링"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("🐛🐛🐛 지그재그 리뷰 크롤링 시작...")
            
            # 상품 ID 추출
            import re
            match = re.search(r'products/(\d+)', product_url)
            if not match:
                raise Exception("상품 ID를 찾을 수 없습니다")
            
            product_id = match.group(1)
            review_url = f"https://zigzag.kr/review/list/{product_id}"
            
            print(f"📦 상품 ID: {product_id}")
            print("📄 리뷰 페이지 접속...")
            await page.goto(review_url, wait_until='networkidle')
            
            print("📜 스크롤하여 모든 리뷰 로드...")
            for i in range(5):
                await page.evaluate('() => window.scrollBy(0, window.innerHeight)')
                await asyncio.sleep(1)
            
            print("🔍 리뷰 데이터 추출 중...")
            review_data = await page.evaluate('''() => {
                const reviews = [];
                const containers = document.querySelectorAll("div.css-1j47pg4.eimmef70");
                
                containers.forEach((container, index) => {
                    const text = container.innerText || "";
                    if (text.length > 10) {
                        reviews.push({
                            id: index + 1,
                            text: text
                        });
                    }
                });
                
                return reviews;
            }''')
            
            print(f"📝 발견된 리뷰: {len(review_data)}개")
            
            # JSON 파일로 저장
            output_path = "data/review-data.json"
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(review_data, f, ensure_ascii=False, indent=2)
            
            print(f"💾 리뷰 데이터 저장 완료: {output_path}")
            
            print("\n🎉 크롤링 완료!")
            print(f"📊 결과 요약:")
            print(f"   - 상품 ID: {product_id}")
            print(f"   - 리뷰 개수: {len(review_data)}개")
            print(f"   - 데이터 파일: {output_path}")
            
            # 첫 번째 리뷰 샘플 출력
            if review_data:
                print(f"\n📝 첫 번째 리뷰 샘플:")
                print(f"ID: {review_data[0]['id']}")
                print(f"텍스트: {review_data[0]['text'][:150]}...")
            
            return {
                'success': True,
                'product_id': product_id,
                'reviewCount': len(review_data),
                'reviews': review_data
            }
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            raise e
        finally:
            await browser.close()

async def main():
    """메인 함수"""
    try:
        result = await complete_crawl("https://zigzag.kr/catalog/products/0000") #크롤링할 상품 주소 입력
        print("\n✅ 모든 작업이 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 실행 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())