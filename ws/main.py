import fitz  # PyMuPDF
import os
import re
import json
from PIL import Image, ImageChops

# ==========================================
# ✂️ 여백 제거 및 노이즈 필터링
# ==========================================
def trim_all_whitespace(image_path):
    try:
        img = Image.open(image_path).convert("RGB")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        
        diff = ImageChops.add(diff, diff, 2.0, -150)
        bbox = diff.getbbox() 
        
        if bbox:
            padding = 10
            left = max(0, bbox[0] - padding)
            top = max(0, bbox[1] - padding)
            right = min(img.width, bbox[2] + padding)
            bottom = min(img.height, bbox[3] + padding)
            
            cropped_img = img.crop((left, top, right, bottom))
            cropped_img.save(image_path, quality=100)
    except Exception as e:
        print(f"여백 제거 오류: {e}")

def extract_smart_problems_high_res(pdf_path, output_folder="Chemistry_Dashboard"):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    print(f"[{pdf_path}] 🤖 문제 확대 + 칼각 여백 제거 추출을 시작합니다...\n")
    doc = fitz.open(pdf_path)
    
    problem_images = []
    problem_pattern = re.compile(r"^\s*([0-9]{1,2})\s*(?:\.|\n| )")
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_text = page.get_text("text")
        
        score = 0
        score += page_text.count('옳은 것은') * 3
        score += page_text.count('옳지 않은 것은') * 3
        score += page_text.count('고른 것은') * 3
        score += page_text.count('그림은') * 2
        score += page_text.count('표는') * 2
        
        circle_count = sum(page_text.count(c) for c in ['①', '②', '③', '④', '⑤'])
        score += (circle_count // 5) * 3
        
        score -= page_text.count('핵심 내용') * 10
        score -= page_text.count('단원 시작하기') * 10
        score -= page_text.count('비법 특강') * 10
        score -= page_text.count('개념 확인') * 10
        
        if score < 5:
            continue
            
        print(f" 🟢 {page_num + 1}쪽: [문제 추출 중...]")

        page_width = page.rect.width
        page_height = page.rect.height
        blocks = page.get_text("blocks")
        
        left_blocks = []
        right_blocks = []
        
        for b in blocks:
            if b[6] != 0: continue 
            x0, y0, x1, y1 = b[:4]
            if y0 < 40 or y1 > page_height - 40: continue
            
            if x0 < page_width / 2:
                left_blocks.append(b)
            else:
                right_blocks.append(b)
                
        def get_problem_splits(col_blocks):
            if not col_blocks: return []
            col_blocks.sort(key=lambda x: x[1])
            min_x = min([b[0] for b in col_blocks]) if col_blocks else 0
            splits = []
            for b in col_blocks:
                x0, y0, text = b[0], b[1], b[4]
                if problem_pattern.match(text) and (x0 - min_x) < 25:
                    if not splits or (y0 - splits[-1] > 40):
                        splits.append(y0)
            return splits

        left_splits = get_problem_splits(left_blocks)
        right_splits = get_problem_splits(right_blocks)
        
        def crop_and_save(splits, is_left, start_idx):
            rects = []
            x_start = 0 if is_left else (page_width / 2) + 10
            x_end = (page_width / 2) - 10 if is_left else page_width
            
            for i in range(len(splits)):
                y_top = max(0, splits[i] - 10)
                if i + 1 < len(splits):
                    y_bottom = splits[i+1] - 5
                else:
                    y_bottom = page_height - 30
                
                if y_bottom - y_top > 50:
                    rects.append(fitz.Rect(x_start, y_top, x_end, y_bottom))
            
            for i, rect in enumerate(rects):
                mat = fitz.Matrix(4.0, 4.0) 
                pix = page.get_pixmap(matrix=mat, clip=rect)
                
                img_name = f"prob_p{page_num+1:03d}_{start_idx + i}.png"
                img_path = os.path.join(output_folder, img_name)
                pix.save(img_path)
                
                trim_all_whitespace(img_path)
                
                problem_images.append({
                    "page": page_num + 1,
                    "file": img_name
                })
            return len(rects)
            
        saved_left = crop_and_save(left_splits, True, 1)
        saved_right = crop_and_save(right_splits, False, saved_left + 1)

    print(f"\n🎉 총 {len(problem_images)}개의 문제가 추출되었습니다!")

    # 3. 대시보드 HTML 생성
    js_problems = json.dumps(problem_images)
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>오답 모의고사 대시보드</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background-color: #f5f5f5; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
            .header {{ background: #fff; border-bottom: 1px solid #f0f0f0; padding: 0 24px; height: 64px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06); z-index: 10; }}
            .header-title {{ font-size: 20px; font-weight: 600; color: #1f1f1f; display: flex; align-items: center; gap: 10px; }}
            .ant-btn {{ cursor: pointer; height: 36px; padding: 4px 20px; font-size: 14px; font-weight: 500; border-radius: 6px; border: 1px solid transparent; transition: all 0.2s; }}
            .ant-btn-primary {{ color: #fff; background: #1677ff; }}
            .ant-btn-primary:hover {{ background: #4096ff; transform: translateY(-1px); }}
            .ant-btn-danger {{ color: #ff4d4f; background: #fff; border-color: #ff4d4f; height: 30px; font-size: 13px; }}
            .ant-btn-danger:hover {{ background: #fff2f0; }}
            .layout-content {{ display: flex; flex: 1; overflow: hidden; }}
            .main-viewer {{ flex: 1; background: #ebedf0; display: flex; flex-direction: column; overflow: hidden; }}
            .viewer-toolbar {{ padding: 12px 24px; background: #fff; border-bottom: 1px solid #d9d9d9; display: flex; align-items: center; justify-content: space-between; }}
            .scroll-area {{ flex: 1; overflow-y: auto; padding: 24px; }}
            .problem-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 24px; align-items: start; }}
            .grid-item {{ background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); cursor: pointer; transition: 0.2s; border: 2px solid transparent; position: relative; display: flex; flex-direction: column; align-items: center; }}
            .grid-item:hover {{ transform: translateY(-4px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); border-color: #91caff; }}
            .grid-item.selected {{ border-color: #1677ff; background: #e6f4ff; box-shadow: 0 4px 12px rgba(22, 119, 255, 0.2); }}
            .grid-item img {{ max-width: 100%; object-fit: contain; margin-top: 15px; border-radius: 4px; }}
            .page-badge {{ background: #f0f0f0; color: #595959; font-size: 13px; padding: 6px 10px; border-radius: 6px; font-weight: bold; align-self: flex-start; }}
            .sidebar-right {{ width: 400px; background: #fff; border-left: 1px solid #f0f0f0; display: flex; flex-direction: column; }}
            .cart-header {{ padding: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f0f0f0; background: #fafafa; }}
            .problem-cart {{ flex: 1; overflow-y: auto; padding: 20px; background: #fbfbfb; }}
            .cart-item {{ background: #fff; border: 1px solid #e8e8e8; border-radius: 8px; padding: 15px; margin-bottom: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }}
            .cart-item img {{ width: 100%; display: block; border-radius: 4px; }}
            .empty-state {{ text-align: center; padding: 60px 20px; color: #bfbfbf; line-height: 1.6; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-title">📝 오답 모의고사 대시보드 (문제 꽉 채움 버전)</div>
            <button class="ant-btn ant-btn-primary" onclick="generatePDF()">🖨️ 시험지로 크게 출력하기 ▶</button>
        </div>
        <div class="layout-content">
            <div class="main-viewer">
                <div class="viewer-toolbar">
                    <span style="font-weight: 600; font-size: 16px;">📚 전체 문제 갤러리</span>
                </div>
                <div class="scroll-area"><div class="problem-grid" id="problem-grid"></div></div>
            </div>
            <div class="sidebar-right">
                <div class="cart-header">
                    <span style="font-weight: bold; font-size: 16px;">내 시험지 장바구니</span>
                    <span style="color: #1677ff; font-weight: 800; font-size: 18px;" id="count-label">0 개</span>
                </div>
                <div class="problem-cart" id="cart">
                    <div class="empty-state" id="empty-state">장바구니가 비어있습니다.</div>
                </div>
            </div>
        </div>
        <script>
            const problems = {js_problems};
            const selectedProblems = new Set();
            const gridEl = document.getElementById('problem-grid');
            const cartEl = document.getElementById('cart');
            const emptyState = document.getElementById('empty-state');
            const countLabel = document.getElementById('count-label');

            function init() {{
                problems.forEach((prob, index) => {{
                    const div = document.createElement('div');
                    div.className = 'grid-item';
                    div.id = `item-${{index}}`;
                    div.innerHTML = `<div class="page-badge">Page ${{prob.page}}</div><img src="${{prob.file}}" loading="lazy">`;
                    div.onclick = () => toggleProblem(index, prob);
                    gridEl.appendChild(div);
                }});
            }}

            function toggleProblem(index, prob) {{
                const itemEl = document.getElementById(`item-${{index}}`);
                if (selectedProblems.has(index)) {{
                    selectedProblems.delete(index);
                    itemEl.classList.remove('selected');
                    const cartItem = document.getElementById(`cart-${{index}}`);
                    if(cartItem) cartItem.remove();
                }} else {{
                    selectedProblems.add(index);
                    itemEl.classList.add('selected');
                    emptyState.style.display = 'none';
                    const cartItem = document.createElement('div');
                    cartItem.className = 'cart-item';
                    cartItem.id = `cart-${{index}}`;
                    cartItem.innerHTML = `
                        <div style="display: flex; justify-content: space-between; margin-bottom: 12px; align-items: center;">
                            <div class="page-badge" style="background:#e6f4ff; color:#1677ff;">Page ${{prob.page}}</div>
                            <button class="ant-btn-danger" onclick="event.stopPropagation(); toggleProblem(${{index}}, problems[${{index}}])">삭제</button>
                        </div>
                        <img src="${{prob.file}}">
                    `;
                    cartEl.appendChild(cartItem);
                    cartEl.scrollTop = cartEl.scrollHeight;
                }}
                updateCount();
            }}

            function updateCount() {{
                countLabel.innerText = `${{selectedProblems.size}} 개`;
                if (selectedProblems.size === 0) emptyState.style.display = 'block';
            }}

            // 🌟 꽉 채운 2x2 모의고사 인쇄 로직 (크기 대폭 확대)
            function generatePDF() {{
                if (selectedProblems.size === 0) {{ alert('장바구니에 문제가 없습니다!'); return; }}
                const selectedImages = Array.from(cartEl.querySelectorAll('.cart-item img')).map(img => img.src);
                
                const win = window.open('', '_blank');
                let html = `
                    <html><head><title>나만의 오답 모의고사</title>
                    <style>
                        @page {{ size: A4; margin: 8mm; }} /* 종이 가장자리 여백 최소화 */
                        body {{ font-family: 'Malgun Gothic', sans-serif; margin: 0; background: #525659; }}
                        .page {{ 
                            width: 210mm; height: 297mm; background: white; margin: 20px auto; 
                            padding: 10mm 12mm; box-sizing: border-box; position: relative;
                            page-break-after: always; display: flex; flex-direction: column;
                            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
                        }}
                        @media print {{
                            body {{ background: white; }}
                            .page {{ margin: 0; box-shadow: none; width: 100%; height: 100vh; border: none; padding: 8mm 10mm; }}
                        }}
                        .header {{ 
                            display: flex; justify-content: space-between; align-items: flex-end; 
                            border-bottom: 2px solid #2b6cb0; padding-bottom: 8px; margin-bottom: 15px; 
                        }}
                        .title {{ font-size: 22px; font-weight: 900; color: #333; letter-spacing: -1px; }}
                        .name-sec {{ font-size: 16px; font-weight: bold; }}
                        
                        /* 그리드 여백(gap) 줄여서 이미지 공간 100% 확보 */
                        .grid {{ 
                            flex: 1; display: grid; 
                            grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; 
                            gap: 15px 25px; position: relative; 
                        }}
                        .grid::after {{ content: ''; position: absolute; top: 0; bottom: 0; left: 50%; border-left: 1px dashed #bbb; transform: translateX(-50%); }}
                        .grid::before {{ content: ''; position: absolute; top: 50%; left: 0; right: 0; border-top: 1px dashed #bbb; transform: translateY(-50%); }}
                        
                        .cell {{ display: flex; flex-direction: column; position: relative; z-index: 10; background: white; padding: 5px; overflow: hidden; height: 100%; }}
                        .cell-num {{ font-size: 18px; font-weight: 900; margin-bottom: 5px; color: #1677ff; flex-shrink: 0; }}
                        
                        /* 이미지 높이 제한 해제 (60% -> 100%로 변경) */
                        .img-wrapper {{ flex: 1; display: flex; align-items: flex-start; overflow: hidden; }}
                        .img-wrapper img {{ max-width: 100%; max-height: 100%; object-fit: contain; object-position: top left; }}
                    </style></head><body>
                `;
                
                for(let i = 0; i < selectedImages.length; i += 4) {{
                    html += `
                        <div class="page">
                            <div class="header">
                                <div class="title">[오답 모의고사] 완자 화학</div>
                                <div class="name-sec">이름 : ____________________</div>
                            </div>
                            <div class="grid">
                    `;
                    
                    for(let j = 0; j < 4; j++) {{
                        if(i + j < selectedImages.length) {{
                            html += `
                                <div class="cell">
                                    <div class="cell-num">${{i + j + 1}}번</div>
                                    <div class="img-wrapper"><img src="${{selectedImages[i + j]}}"></div>
                                </div>
                            `;
                        }} else {{
                            html += `<div class="cell"></div>`;
                        }}
                    }}
                    html += `</div></div>`;
                }}
                
                html += `</body></html>`;
                win.document.write(html);
                win.document.close(); win.focus();
                
                setTimeout(() => {{ win.print(); }}, 800);
            }}
            window.onload = init;
        </script>
    </body>
    </html>
    """
    
    html_file = os.path.join(output_folder, "dashboard.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"\n✅ 완료! '{output_folder}' 폴더의 'dashboard.html'을 실행하세요.")

if __name__ == "__main__":
    target_pdf = "포물선_합치기.pdf" 
    extract_smart_problems_high_res(target_pdf)