# OCR 系統完整部署教學

## 系統架構

```
使用者瀏覽器
     │
     ▼
[前端 Nginx :80]  ←→  [後端 FastAPI :8000]
                              │
                              ▼
                   /opt/ocr-storage/ (VM 永久儲存)
                   ├── uploads/   (原始圖片)
                   └── results/   (TXT + ZIP)
```

---

## 第一步：Windows 開發電腦上的準備

### 1.1 安裝必要工具（Windows）

```powershell
# 安裝 Git（若還沒有）
winget install Git.Git

# 安裝 Python（若還沒有）
winget install Python.Python.3.11
```

### 1.2 本機測試（可選）

```powershell
# 進入後端目錄
cd ocr-app\backend

# 建立虛擬環境
python -m venv venv
venv\Scripts\activate

# 安裝依賴
pip install -r requirements.txt

# 需要先在 Windows 安裝 Tesseract：
# 下載：https://github.com/UB-Mannheim/tesseract/wiki
# 安裝後預設路徑：C:\Program Files\Tesseract-OCR\tesseract.exe

# 啟動後端
uvicorn main:app --reload --port 8000
```

然後用瀏覽器打開 `frontend/index.html` 即可本機測試。

---

## 第二步：SSH 連線到 Oracle Cloud VM

```bash
# 使用你的 VM 公開 IP 和 private key 連線
ssh -i ~/.ssh/your-private-key.pem opc@<你的VM公開IP>
```

> **注意**：Oracle Cloud 的預設使用者是 `opc`（Oracle Linux）

---

## 第三步：VM 初始環境設定

### 3.1 更新系統

```bash
sudo dnf update -y
```

### 3.2 安裝 Podman 和 podman-compose

```bash
sudo dnf install -y podman

# 安裝 podman-compose（Python 版）
sudo dnf install -y python3-pip
sudo pip3 install podman-compose
```

### 3.3 確認安裝

```bash
podman --version       # 應顯示 podman version x.x.x
podman-compose version # 應顯示版本號
```

### 3.4 建立永久儲存目錄

```bash
# 建立儲存目錄（此目錄的檔案永遠保存在 VM 上，不會因為容器重啟而消失）
sudo mkdir -p /opt/ocr-storage/uploads
sudo mkdir -p /opt/ocr-storage/results

# 設定權限
sudo chown -R $USER:$USER /opt/ocr-storage
chmod -R 755 /opt/ocr-storage

# 確認目錄存在
ls -la /opt/ocr-storage/
```

---

## 第四步：設定防火牆

### 4.1 VM 內部防火牆（firewalld）

```bash
# 開放 80 埠（前端）和 8000 埠（後端 API）
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# 確認設定
sudo firewall-cmd --list-ports
```

### 4.2 Oracle Cloud 控制台防火牆（必做！）

1. 登入 [OCI Console](https://cloud.oracle.com)
2. 選擇你的 VM 所在的 **VCN（Virtual Cloud Network）**
3. 點選 **Security Lists** → **Default Security List**
4. 新增 **Ingress Rules（入站規則）**：

| 來源 CIDR    | IP Protocol | 目標 Port Range | 說明     |
|-------------|-------------|-----------------|--------|
| 0.0.0.0/0   | TCP         | 80              | 前端網頁 |
| 0.0.0.0/0   | TCP         | 8000            | 後端 API |

---

## 第五步：上傳程式碼到 VM

### 方法 A：用 scp 上傳（從 Windows 執行）

```powershell
# 在 Windows PowerShell 執行
# 把整個 ocr-app 資料夾傳到 VM
scp -i C:\Users\你的名字\.ssh\your-key.pem -r .\ocr-app opc@<VM公開IP>:/home/opc/
```

### 方法 B：用 Git（推薦）

```bash
# 在 VM 上執行
cd /home/opc
git clone https://github.com/你的帳號/你的repo.git ocr-app
```

### 方法 C：直接在 VM 上建立檔案

```bash
mkdir -p /home/opc/ocr-app/{backend,frontend}

# 然後用 nano 或 vi 建立每個檔案：
nano /home/opc/ocr-app/backend/main.py
nano /home/opc/ocr-app/backend/requirements.txt
nano /home/opc/ocr-app/backend/Dockerfile
nano /home/opc/ocr-app/frontend/index.html
nano /home/opc/ocr-app/frontend/Dockerfile
nano /home/opc/ocr-app/frontend/nginx.conf
nano /home/opc/ocr-app/podman-compose.yml
```

---

## 第六步：建置並啟動容器

```bash
# 進入專案目錄
cd /home/opc/ocr-app

# 建置容器映像（第一次需要幾分鐘，因為要下載 Tesseract）
podman-compose build

# 啟動所有容器（背景執行）
podman-compose up -d

# 查看容器狀態（確認都是 Up 狀態）
podman ps

# 查看後端 log（確認有啟動成功）
podman logs ocr-backend
```

### 成功啟動的樣子：

```
CONTAINER ID  IMAGE           COMMAND              STATUS
abc123        ocr-backend     uvicorn main:app...  Up 2 minutes
def456        ocr-frontend    nginx -g daemon...   Up 2 minutes
```

---

## 第七步：測試系統

```bash
# 在 VM 上測試後端是否正常
curl http://localhost:8000/health

# 預期回應：
# {"status":"ok","storage":"/app/storage"}
```

然後在你的瀏覽器打開：
- **前端**：`http://<VM公開IP>/`
- **後端 API 文件**：`http://<VM公開IP>:8000/docs`

---

## 常用管理指令

```bash
# 查看所有容器
podman ps -a

# 停止所有容器
podman-compose down

# 重新啟動
podman-compose restart

# 查看後端即時 log
podman logs -f ocr-backend

# 查看前端 log
podman logs -f ocr-frontend

# 重新 build（修改程式碼後）
podman-compose build
podman-compose up -d

# 查看已儲存的檔案（永久儲存在 VM 上）
ls -lh /opt/ocr-storage/uploads/
ls -lh /opt/ocr-storage/results/
```

---

## 關於永久儲存

**是的，所有檔案都會永久保存在 VM 上！**

```
/opt/ocr-storage/
├── uploads/          ← 使用者上傳的原始圖片
│   ├── 20240101_abc12345.jpg
│   └── 20240101_def67890.png
└── results/          ← 辨識結果
    ├── 20240101_abc12345_result.txt
    ├── 20240101_abc12345_package.zip  ← 含圖片+txt 的打包檔
    ├── 20240101_def67890_result.txt
    └── 20240101_def67890_package.zip
```

- 容器重啟：**不影響** — 檔案在 VM 的磁碟上，不在容器內
- VM 重開機：**不影響** — `/opt/ocr-storage` 是 VM 的本地磁碟
- 容器重建（`podman-compose build`）：**不影響** — 資料目錄獨立掛載

**使用者下載方式**：
1. 辨識完成後，頁面直接出現「下載完整包」和「只下載 TXT」按鈕
2. 歷史頁面也可以重複下載之前的結果

---

## VM 重開機後自動啟動（選用）

```bash
# 建立 systemd service
sudo tee /etc/systemd/system/ocr-app.service > /dev/null <<EOF
[Unit]
Description=OCR Application
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=opc
WorkingDirectory=/home/opc/ocr-app
ExecStart=/usr/local/bin/podman-compose up -d
ExecStop=/usr/local/bin/podman-compose down

[Install]
WantedBy=multi-user.target
EOF

# 啟用自動啟動
sudo systemctl daemon-reload
sudo systemctl enable ocr-app
sudo systemctl start ocr-app

# 確認狀態
sudo systemctl status ocr-app
```

---

## 常見問題排解

### Q: 瀏覽器打不開，無法連線
```bash
# 確認容器在跑
podman ps

# 確認埠有在監聽
ss -tlnp | grep -E '80|8000'

# 確認防火牆
sudo firewall-cmd --list-ports

# 確認 OCI Console 的 Security List 有開放 80 和 8000
```

### Q: OCR 辨識出來是亂碼或空的
```bash
# 確認 Tesseract 語言包安裝成功
podman exec ocr-backend tesseract --list-langs
# 應該看到 chi_tra、chi_sim、eng
```

### Q: 上傳檔案失敗
```bash
# 確認儲存目錄權限
ls -la /opt/ocr-storage/
# 確認容器掛載成功
podman inspect ocr-backend | grep -A5 Mounts
```

### Q: 磁碟空間不足
```bash
# 查看磁碟使用量
df -h /opt/ocr-storage/

# 查看哪些檔案最大
du -sh /opt/ocr-storage/* | sort -rh | head -20

# 手動清除舊結果（謹慎操作）
# rm /opt/ocr-storage/uploads/舊檔案名稱
```
