#!/usr/bin/env bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/billpanel"
BIN_PATH="/usr/bin/billpanel"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    print_info "Checking dependencies..."
    
    local missing_deps=()
    
    if ! command -v python &> /dev/null; then
        missing_deps+=("python")
    fi
    
    if ! command -v uv &> /dev/null; then
        missing_deps+=("uv")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        print_info "Install them with: sudo pacman -S ${missing_deps[*]}"
        exit 1
    fi
    
    print_success "All dependencies are installed"
}

backup_existing() {
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Found existing installation at $INSTALL_DIR"
        local backup_dir="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
        print_info "Creating backup at $backup_dir"
        sudo mv "$INSTALL_DIR" "$backup_dir"
        print_success "Backup created"
    fi
}

install_app() {
    print_info "Installing billpanel to $INSTALL_DIR..."
    
    # Create installation directory
    sudo mkdir -p "$INSTALL_DIR"
    
    # Copy project files
    print_info "Copying project files..."
    sudo cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/"
    
    # Create and setup virtual environment
    print_info "Creating virtual environment..."
    cd "$INSTALL_DIR"
    sudo python -m venv .venv
    
    # Install dependencies
    print_info "Installing dependencies..."
    sudo uv sync --no-dev --frozen
    
    # Create launcher script
    print_info "Creating launcher script..."
    sudo tee "$BIN_PATH" > /dev/null << 'EOF'
#!/bin/sh
cd /opt/billpanel
exec .venv/bin/python run.py "$@"
EOF
    
    sudo chmod +x "$BIN_PATH"
    
    # Set proper permissions for styles directory
    if [ -d "$INSTALL_DIR/src/billpanel/styles" ]; then
        print_info "Setting permissions for styles directory..."
        sudo chmod -R a+rwX "$INSTALL_DIR/src/billpanel/styles"
        sudo find "$INSTALL_DIR/src/billpanel/styles" -type d -exec chmod 777 {} +
        sudo find "$INSTALL_DIR/src/billpanel/styles" -type f -exec chmod 666 {} +
    fi
    
    print_success "Installation completed!"
}

cleanup() {
    print_info "Cleaning up build artifacts..."
    cd "$PROJECT_DIR"
    
    # Clean Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    
    print_success "Cleanup completed"
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Install billpanel locally to replace the current installation.

OPTIONS:
    -h, --help              Show this help message
    -n, --no-backup         Don't create backup of existing installation
    -c, --cleanup           Clean up after installation
    --uninstall             Uninstall billpanel

EXAMPLES:
    $0                      # Install with backup
    $0 --no-backup          # Install without backup
    $0 --cleanup            # Install and cleanup
    $0 --uninstall          # Uninstall billpanel

EOF
}

uninstall() {
    print_warning "Uninstalling billpanel..."
    
    if [ -d "$INSTALL_DIR" ]; then
        print_info "Removing $INSTALL_DIR..."
        sudo rm -rf "$INSTALL_DIR"
    fi
    
    if [ -f "$BIN_PATH" ]; then
        print_info "Removing $BIN_PATH..."
        sudo rm -f "$BIN_PATH"
    fi
    
    print_success "Billpanel has been uninstalled"
    exit 0
}

# Main script
main() {
    local do_backup=true
    local do_cleanup=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -n|--no-backup)
                do_backup=false
                shift
                ;;
            -c|--cleanup)
                do_cleanup=true
                shift
                ;;
            --uninstall)
                uninstall
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Billpanel Local Installation      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
    
    # Check if running with sudo
    if [ "$EUID" -eq 0 ]; then
        print_error "Don't run this script as root or with sudo"
        print_info "The script will ask for sudo when needed"
        exit 1
    fi
    
    # Check dependencies
    check_dependencies
    
    # Backup existing installation
    if [ "$do_backup" = true ]; then
        backup_existing
    fi
    
    # Install
    install_app
    
    # Cleanup if requested
    if [ "$do_cleanup" = true ]; then
        cleanup
    fi
    
    echo ""
    print_success "Billpanel has been installed successfully!"
    echo ""
    print_info "You can now run: billpanel"
    print_info "Or with debug mode: billpanel --debug"
    echo ""
    
    # Show backup location if created
    if [ "$do_backup" = true ]; then
        local latest_backup=$(ls -td ${INSTALL_DIR}.backup.* 2>/dev/null | head -1)
        if [ -n "$latest_backup" ]; then
            print_info "Backup saved at: $latest_backup"
            print_warning "To restore: sudo rm -rf $INSTALL_DIR && sudo mv $latest_backup $INSTALL_DIR"
        fi
    fi
    
    echo ""
}

# Run main function
main "$@"
