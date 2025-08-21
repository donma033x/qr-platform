QR Platform
QR Platform 是一个基于 Python 和 FastAPI 的 Web 应用，提供二维码生成、解码和图片文字提取（OCR）功能。项目使用 easyocr 进行中英文 OCR，支持离线运行（无需联网下载模型），并通过 Docker 部署以确保环境一致性。
功能

二维码生成 (/generate): 生成包含文本的二维码，支持压缩、自定义颜色和添加 Logo。
二维码解码 (/decode): 从图片中解码二维码，支持压缩文本的自动解压。
OCR 文字提取 (/ocr): 从图片中提取中英文文字，使用 easyocr 支持 en 和 ch_sim 语言。
统计信息 (/stats): 显示生成、解码和 OCR 操作的统计数据。
日志导出 (/logs/export): 以 CSV 格式导出操作日志。
健康检查 (/health): 检查服务状态。

依赖项

Python 3.12
FastAPI, Uvicorn, OpenCV (opencv-python), EasyOCR, Tesseract-OCR
Docker（用于容器化部署）
UV（用于依赖管理，推荐）

安装和运行（本地）
前提条件

安装 Python 3.12
安装 UV（推荐用于依赖管理）:pip install uv


安装系统依赖（Linux/Debian 示例）:sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim libgl1 libglib2.0-0



安装步骤

克隆仓库：
git clone https://github.com/<你的用户名>/qr-platform.git
cd qr-platform


安装 Python 依赖：
uv sync --frozen


下载 EasyOCR 模型（确保离线运行）：
python -c "import easyocr; reader = easyocr.Reader(['en', 'ch_sim'], gpu=False)"
mkdir -p models/EasyOCR
cp -r ~/.EasyOCR/* models/EasyOCR/


运行应用：
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000


访问 Web 界面：打开浏览器，访问 http://localhost:8000。


Docker 部署
构建镜像

确保 models/EasyOCR/ 包含预下载的模型文件（参考“安装步骤”中的第 3 步）。
构建 Docker 镜像：docker build -t qr-platform .



运行容器
docker run -d -p 8000:8000 --name qr-platform qr-platform:latest


访问 http://localhost:8000 测试 Web 界面。
使用 --network none 验证离线运行：docker run -d -p 8000:8000 --name qr-platform --network none qr-platform:latest



API 使用示例
使用 curl 测试主要端点：
生成二维码
curl -X POST http://localhost:8000/generate \
  -F "text=这是一个测试二维码，包含中文和英文: Hello, World!" \
  -F "compress=true" \
  -F "color=#FF0000" \
  -F "bg_color=#FFFFFF" \
  -o generated_qr.png

解码二维码
curl -X POST http://localhost:8000/decode \
  -F "image=@generated_qr.png" \
  -o decode_result.json

OCR 文字提取
curl -X POST http://localhost:8000/ocr \
  -F "image=@text_image.jpg" \
  -o ocr_result.json

其他端点

统计：curl -X GET http://localhost:8000/stats
日志导出：curl -X GET http://localhost:8000/logs/export -o logs.csv
健康检查：curl -X GET http://localhost:8000/health

项目结构
qr-platform/
├── app/
│   └── main.py        # FastAPI 应用
├── templates/
│   └── index.html    # Web 界面
├── static/           # 静态文件
├── models/
│   └── EasyOCR/      # EasyOCR 模型文件
├── pyproject.toml    # 依赖配置文件
├── uv.lock           # UV 依赖锁文件
├── Dockerfile        # Docker 配置
├── README.md         # 项目说明

注意事项

速率限制：/generate、/decode 和 /ocr 端点每 IP 每分钟限制 5 次请求。
EasyOCR 模型：确保 models/EasyOCR/ 包含 craft_mlt_25k.pth、english_g2.pth 和 ch_sim_g2.pth，以支持离线 OCR。
内网部署：如需在内网环境中运行，传输完整项目目录并重新构建镜像，避免使用 podman export（可能丢失元数据）。

故障排查

模块导入错误（如 Could not import module app.main）：
确保 /app/app/main.py 存在。
检查虚拟环境：docker exec qr-platform ls -l /app/.venv/bin/uvicorn。


OCR 失败：
确认 models/EasyOCR/ 包含模型文件。
检查日志：docker logs qr-platform 或 SELECT * FROM logs WHERE action='ocr_error'。


Docker 构建慢：
使用国内镜像源（如阿里云）：RUN echo "deb http://mirrors.aliyun.com/debian bookworm main" > /etc/apt/sources.list





许可证
MIT License
