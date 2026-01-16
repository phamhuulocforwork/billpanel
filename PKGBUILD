# Maintainer: Dmitry <dimflix.official@gmail.com>
pkgname=billpanel-git
conflicts=('billpanel')
provides=('billpanel')
pkgver=r1.0.0
pkgrel=1
pkgdesc="🎯 Elegant and extensible status bar (forked from mewline)"
arch=('any')
url="https://github.com/phamhuulocforwork/billpanel"
license=('MIT')
depends=(
  'python'
  'power-profiles-daemon'
  'gnome-bluetooth-3.0'
  'dart-sass'
  'gobject-introspection'
  'gray-git'
  'fabric-cli'
  'tesseract'
  'tesseract-data-eng'
  'tesseract-data-rus'
  'cliphist'
)
makedepends=(
  'python-uv'
  'git'
  'python-virtualenv'
)
options=('!debug')
source=("git+$url.git")
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/billpanel"
  printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

package() {
  cd "$srcdir/billpanel"

  # Install virtual environment
  install -d -m755 "$pkgdir/opt/billpanel"
  python -m venv "$pkgdir/opt/$pkgname/.venv"
  uv sync --no-dev --frozen --compile-bytecode

  # Install application files
  cp -r . "$pkgdir/opt/billpanel/"

  # Create launch script
  install -Dm755 /dev/stdin "$pkgdir/usr/bin/billpanel" << EOF
#!/bin/sh
cd /opt/billpanel-git
exec .venv/bin/python run.py "\$@"
EOF

  # Granting rights to files and folders
  chmod -R a+rwX "$pkgdir/opt/billpanel/src/mewline/styles"
  find "$pkgdir/opt/billpanel/src/mewline/styles" -type d -exec chmod 777 {} +
  find "$pkgdir/opt/billpanel/src/mewline/styles" -type f -exec chmod 666 {} +
  chmod 755 "$pkgdir/usr/bin/mewline"
}
