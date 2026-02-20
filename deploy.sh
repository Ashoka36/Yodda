#!/bin/bash
set -e

# Update and install dependencies
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip nginx git

# Clone the repository
if [ -d "Yodda" ]; then
  rm -rf Yodda
fi
git clone https://github.com/Ashoka36/Yodda.git
cd Yodda

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
pip install gunicorn

# Create systemd service file
sudo tee /etc/systemd/system/yodda.service > /dev/null <<EOF
[Unit]
Description=Yodda Premium FastAPI Application
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/root/Yodda
ExecStart=/root/Yodda/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker app_complete:app --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start and enable the service
sudo systemctl daemon-reload
sudo systemctl start yodda
sudo systemctl enable yodda

echo "Deployment complete. Yodda is now running."
