# app/main.py
# FastAPI QR 码平台
# 功能：
# 1. QR 码生成：使用 qrcode，支持超长文本（zlib 压缩），自定义颜色、Logo，后台自动 L 级纠错（最大容量）
# 2. QR 码解码：使用 opencv-python（纯 Python）
# 3. OCR：使用 easyocr（纯 Python，CPU 模式）提取文字/图表，保留转行格式
# 4. 日志审计：记录 IP、时间、操作，展示统计
# 5. Web 界面：全中文，科技感设计，支持暗/亮模式
# 6. API：生成、解码、OCR、统计、日志导出
# 7. 速率限制：每 IP 每分钟 5 次请求

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import qrcode
from PIL import Image, ImageDraw, ImageEnhance
import cv2
import numpy as np
import easyocr
import io
import zlib
import sqlite3
from datetime import datetime
import csv
import base64
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="二维码平台",
    description="一个现代化的二维码生成与解码服务，支持 OCR 提取文字和图表内容。",
    version="1.0.0"
)

# 速率限制
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS 支持
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 静态文件与模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 数据库设置用于日志
try:
    conn = sqlite3.connect('logs.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT,
        timestamp DATETIME,
        action TEXT,
        details TEXT
    )
    ''')
    conn.commit()
except Exception as e:
    logger.error(f"数据库初始化失败: {str(e)}")
    raise RuntimeError("无法初始化数据库")

# 日志记录函数
def log_action(ip: str, action: str, details: str):
    try:
        cursor.execute("INSERT INTO logs (ip, timestamp, action, details) VALUES (?, ?, ?, ?)",
                      (ip, datetime.now(), action, details))
        conn.commit()
    except Exception as e:
        logger.error(f"日志记录失败: {str(e)}")

# 获取统计
def get_stats():
    try:
        cursor.execute("SELECT COUNT(*) FROM logs WHERE action = 'generate'")
        gen_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM logs WHERE action = 'decode'")
        dec_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM logs WHERE action = 'ocr'")
        ocr_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT ip) FROM logs")
        unique_ips = cursor.fetchone()[0]
        return {"generations": gen_count, "decodings": dec_count, "ocr_extractions": ocr_count, "unique_users": unique_ips}
    except Exception as e:
        logger.error(f"获取统计失败: {str(e)}")
        return {"generations": 0, "decodings": 0, "ocr_extractions": 0, "unique_users": 0}

# 中间件记录请求
@app.middleware("http")
async def log_requests(request: Request, call_next):
    ip = request.client.host
    try:
        response = await call_next(request)
        if request.url.path not in ["/generate", "/decode", "/ocr"]:
            log_action(ip, "access", f"访问 {request.url.path}")
        return response
    except Exception as e:
        logger.error(f"请求处理失败: {str(e)}")
        raise

# 主页
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        stats = get_stats()
        return templates.TemplateResponse("index.html", {"request": request, "stats": stats})
    except Exception as e:
        logger.error(f"主页加载失败: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")

# API: 生成 QR 码
@app.post("/generate")
@limiter.limit("5/minute")
async def generate_qr(
    request: Request,
    text: str = Form(...),
    compress: bool = Form(False),
    color: str = Form("#000000"),
    bg_color: str = Form("#FFFFFF"),
    logo: UploadFile = File(None)
):
    ip = request.client.host
    try:
        if not text:
            raise HTTPException(status_code=400, detail="文本不能为空")
        
        data = text
        if compress:
            data = base64.b64encode(zlib.compress(data.encode('utf-8'))).decode('utf-8') + "|compressed"
        
        # 自动自适应版本（None 让 qrcode 选择最小合适版本），优先 L 级纠错（最大容量）
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(data)
        try:
            qr.make(fit=True)
        except qrcode.exceptions.DataOverflowError:
            # 如果 L 级溢出，尝试 M 级
            qr.error_correction = qrcode.constants.ERROR_CORRECT_M
            try:
                qr.make(fit=True)
            except qrcode.exceptions.DataOverflowError:
                raise HTTPException(status_code=400, detail="文本过长，超出 QR 码容量限制，请缩短文本或启用压缩")
        
        img = qr.make_image(fill_color=color, back_color=bg_color)
        
        if logo:
            try:
                logo_img = Image.open(logo.file).convert("RGBA")
                logo_size = min(img.size) // 4
                logo_img = logo_img.resize((logo_size, logo_size))
                pos = ((img.size[0] - logo_size) // 2, (img.size[1] - logo_size) // 2)
                img.paste(logo_img, pos, logo_img)
            except Exception as e:
                logger.error(f"Logo 处理失败: {str(e)}")
                raise HTTPException(status_code=400, detail="Logo 图像处理失败")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        
        log_action(ip, "generate", f"文本长度: {len(text)}, 压缩: {compress}")
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        log_action(ip, "generate_error", str(e))
        raise HTTPException(status_code=400, detail=str(e))

# API: 解码 QR 码（使用 opencv-python）
@app.post("/decode")
@limiter.limit("5/minute")
async def decode_qr(request: Request, image: UploadFile = File(...)):
    ip = request.client.host
    try:
        # 读取图像
        img = Image.open(image.file).convert('L')  # 灰度化
        img = ImageEnhance.Contrast(img).enhance(3.0)  # 提高对比度
        img = ImageEnhance.Sharpness(img).enhance(2.0)  # 提高锐度
        img_np = np.array(img)  # 转换为 numpy 数组
        
        # 使用 OpenCV QRCodeDetector
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(img_np)
        
        if not data:
            raise HTTPException(status_code=400, detail="未检测到二维码")
        
        if data.endswith("|compressed"):
            try:
                data = zlib.decompress(base64.b64decode(data[:-11])).decode('utf-8')
            except Exception as e:
                raise HTTPException(status_code=400, detail="解压失败，无效的压缩数据")
        
        log_action(ip, "decode", "标准解码成功")
        return {"decoded": data}
    except Exception as e:
        log_action(ip, "decode_error", str(e))
        raise HTTPException(status_code=400, detail=str(e))

# API: OCR 提取文字或图表内容（使用 easyocr）
@app.post("/ocr")
@limiter.limit("5/minute")
async def ocr_image(request: Request, image: UploadFile = File(...)):
    ip = request.client.host
    try:
        img = Image.open(image.file).convert('RGB')  # easyocr 需要 RGB 格式
        img = ImageEnhance.Contrast(img).enhance(2.0)  # 提高对比度
        img = ImageEnhance.Sharpness(img).enhance(2.0)  # 提高锐度
        
        reader = easyocr.Reader(['en', 'ch_sim'], gpu=False)  # CPU 模式
        result = reader.readtext(np.array(img))
        # 保留转行格式，使用 \n 连接
        text = "\n".join([res[1] for res in result]).strip()
        
        if not text:
            raise HTTPException(status_code=400, detail="未检测到文字或图表内容")
        
        log_action(ip, "ocr", "OCR 提取成功")
        return {"text": text}
    except Exception as e:
        log_action(ip, "ocr_error", str(e))
        raise HTTPException(status_code=400, detail=str(e))

# API: 获取统计
@app.get("/stats")
async def stats():
    return get_stats()

# API: 导出日志为 CSV
@app.get("/logs/export")
async def export_logs():
    try:
        cursor.execute("SELECT * FROM logs")
        rows = cursor.fetchall()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ID", "IP", "时间戳", "操作", "详情"])
        writer.writerows(rows)
        buf.seek(0)
        return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=logs.csv"})
    except Exception as e:
        logger.error(f"日志导出失败: {str(e)}")
        raise HTTPException(status_code=500, detail="日志导出失败")

# 健康检查
@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
