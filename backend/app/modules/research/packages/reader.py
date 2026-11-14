"""Research-owned adapter for the shared package reader port."""

from app.modules.research.packages.use_cases import PackageService
from app.shared.contracts import ResearchPackage


class PackageReaderAdapter:
    def __init__(self, service: PackageService):
        self.service = service

    def get_package(self, package_id: str) -> ResearchPackage:
        return self.service.read_package(package_id)
