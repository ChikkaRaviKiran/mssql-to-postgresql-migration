#!/bin/bash

echo "🚀 Setting up MSSQL to PostgreSQL Migration Toolkit"

# Check if running on Ubuntu/Debian
if ! command -v apt-get &> /dev/null; then
    echo "❌ This script requires Ubuntu/Debian with apt-get"
    exit 1
fi

# Install Microsoft ODBC Driver 18 for SQL Server
echo ""
echo "📦 Installing ODBC Driver for SQL Server..."
echo "This may require sudo password for system packages."

# Add Microsoft repository
if [ ! -f /etc/apt/trusted.gpg.d/microsoft.asc ]; then
    echo "Adding Microsoft repository..."
    curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc > /dev/null
fi

# Get Ubuntu version
UBUNTU_VERSION=$(lsb_release -rs)
if [ ! -f /etc/apt/sources.list.d/mssql-release.list ]; then
    echo "Configuring package source for Ubuntu ${UBUNTU_VERSION}..."
    curl https://packages.microsoft.com/config/ubuntu/${UBUNTU_VERSION}/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list > /dev/null
fi

# Update package list
echo "Updating package lists..."
sudo apt-get update

# Install ODBC driver
echo "Installing MSSQL ODBC Driver 18..."
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev

if [ $? -eq 0 ]; then
    echo "✅ ODBC Driver installed successfully"
else
    echo "⚠️  ODBC Driver installation failed or already installed"
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python packages..."

# Check if pip3 is available
if ! command -v pip3 &> /dev/null; then
    echo "Installing pip3..."
    sudo apt-get install -y python3-pip
fi

# Install Python packages
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Python packages installed successfully"
else
    echo "❌ Failed to install Python packages"
    exit 1
fi

# Create .env file from template
echo ""
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo "⚠️  IMPORTANT: Please edit .env file with your actual database credentials"
else
    echo "⚠️  .env file already exists, skipping creation"
fi

# Make scripts executable
echo ""
echo "🔧 Making scripts executable..."
chmod +x test_connection.py migrate.py validate.py export_schema.py rollback.py

echo ""
echo "="*60
echo "✅ Setup complete!"
echo "="*60
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your credentials:"
echo "     nano .env"
echo ""
echo "  2. Test database connections:"
echo "     python3 test_connection.py"
echo ""
echo "  3. Run migration:"
echo "     python3 migrate.py"
echo ""
echo "  4. Validate migration:"
echo "     python3 validate.py"
echo ""
echo "For more options, run: python3 migrate.py --help"
echo ""
