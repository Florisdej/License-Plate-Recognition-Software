#!/bin/bash
# Deploy License Plate Recognition App to Raspberry Pi
# Usage: ./deploy_to_pi.sh [pi_username@pi_hostname]
# Example: ./deploy_to_pi.sh pi@raspberrypi.local

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}License Plate App - Pi Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if target is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: $0 [pi_username@pi_hostname]${NC}"
    echo -e "${YELLOW}Example: $0 pi@raspberrypi.local${NC}"
    exit 1
fi

PI_TARGET=$1
REMOTE_DIR="~/license-plate-app"

echo -e "${YELLOW}Target:${NC} $PI_TARGET"
echo -e "${YELLOW}Remote directory:${NC} $REMOTE_DIR"
echo ""

# Test SSH connection
echo -e "${YELLOW}Testing SSH connection...${NC}"
if ssh -o ConnectTimeout=5 "$PI_TARGET" "echo 'Connection successful'"; then
    echo -e "${GREEN}✓ SSH connection successful${NC}"
else
    echo -e "${RED}✗ Could not connect to $PI_TARGET${NC}"
    echo -e "${YELLOW}Please check:${NC}"
    echo "  1. Raspberry Pi is powered on and connected to network"
    echo "  2. SSH is enabled on the Pi"
    echo "  3. Username and hostname are correct"
    exit 1
fi
echo ""

# Create remote directory
echo -e "${YELLOW}Creating remote directory...${NC}"
ssh "$PI_TARGET" "mkdir -p $REMOTE_DIR"
echo -e "${GREEN}✓ Remote directory ready${NC}"
echo ""

# Files and directories to transfer
FILES_TO_COPY=(
    "App.py"
    "App_Pi.py"
    "Detect.py"
    "Tracker.py"
    "styles.py"
    "Requirements.txt"
    "RASPBERRY_PI_SETUP.md"
    "Data.yaml"
)

DIRS_TO_COPY=(
    "Models"
    "Assets"
)

# Copy files
echo -e "${YELLOW}Copying application files...${NC}"
for file in "${FILES_TO_COPY[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  Copying $file..."
        scp "$file" "$PI_TARGET:$REMOTE_DIR/" || echo -e "${RED}  Warning: Failed to copy $file${NC}"
    else
        echo -e "${YELLOW}  Skipping $file (not found)${NC}"
    fi
done
echo ""

# Copy directories
echo -e "${YELLOW}Copying directories...${NC}"
for dir in "${DIRS_TO_COPY[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "  Copying $dir/..."
        scp -r "$dir" "$PI_TARGET:$REMOTE_DIR/" || echo -e "${RED}  Warning: Failed to copy $dir${NC}"
    else
        echo -e "${YELLOW}  Skipping $dir (not found)${NC}"
    fi
done
echo ""

# Copy model files
echo -e "${YELLOW}Copying YOLO model files...${NC}"
if [ -f "yolo11n.pt" ]; then
    echo "  Copying yolo11n.pt..."
    scp "yolo11n.pt" "$PI_TARGET:$REMOTE_DIR/"
fi
if [ -f "yolov8n.pt" ]; then
    echo "  Copying yolov8n.pt..."
    scp "yolov8n.pt" "$PI_TARGET:$REMOTE_DIR/"
fi
if [ -f "Best.pt" ]; then
    echo "  Copying Best.pt..."
    scp "Best.pt" "$PI_TARGET:$REMOTE_DIR/"
fi
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next steps on your Raspberry Pi:${NC}"
echo ""
echo "1. SSH into your Pi:"
echo "   ssh $PI_TARGET"
echo ""
echo "2. Navigate to the app directory:"
echo "   cd $REMOTE_DIR"
echo ""
echo "3. Create virtual environment:"
echo "   python3 -m venv venv"
echo "   source venv/bin/activate"
echo ""
echo "4. Install dependencies (this takes 30-60 minutes):"
echo "   pip install --upgrade pip"
echo "   pip install -r Requirements.txt"
echo ""
echo "5. Run the optimized Pi version:"
echo "   python3 App_Pi.py"
echo ""
echo -e "${YELLOW}Or run the standard version:${NC}"
echo "   python3 App.py"
echo ""
echo -e "For detailed setup instructions, see ${GREEN}RASPBERRY_PI_SETUP.md${NC} on your Pi."
echo ""
