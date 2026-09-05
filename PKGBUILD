# Maintainer: Denis Bolba <https://github.com/Codder13>
pkgname=ai-cli
pkgver=0.8.0
pkgrel=1
pkgdesc="Ultra-fast streaming AI CLI & agent for Unix terminals"
arch=('any')
url="https://github.com/Codder13/ai-cli"
license=('MIT')
depends=('python' 'python-rich' 'python-pylatexenc')
makedepends=('python-build' 'python-installer' 'python-hatchling')
source=("$pkgname-$pkgver.tar.gz::https://github.com/Codder13/ai-cli/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "ai-cli-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "ai-cli-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
