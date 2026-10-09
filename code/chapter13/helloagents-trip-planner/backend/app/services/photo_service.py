"""景点图片服务：优先高德 POI 实拍，其次维基百科，避免 Unsplash 错配。"""

from typing import Optional, List, Dict, Any
from urllib.parse import quote
import requests

from ..config import get_settings

PREFERRED_TYPES = ("风景名胜", "旅游景点", "博物馆", "世界遗产", "公园", "寺庙", "教堂", "特色商业街", "纪念馆")
PENALIZED_TYPES = ("住宅", "地铁站", "交通设施", "生活服务", "道路名", "公司", "商务住宅")


class PhotoService:
    def __init__(self):
        settings = get_settings()
        self.amap_key = settings.amap_api_key
        self.wiki_headers = {
            "User-Agent": "HelloAgentsTripPlanner/1.0 (educational; photo lookup)"
        }

    def get_attraction_photo(self, name: str, city: str = "") -> Optional[str]:
        if not name:
            return None

        url = self._from_amap(name, city)
        if url:
            return url

        url = self._from_wikipedia(name, city)
        if url:
            return url

        return None

    def _from_amap(self, name: str, city: str) -> Optional[str]:
        if not self.amap_key:
            return None

        try:
            response = requests.get(
                "https://restapi.amap.com/v3/place/text",
                params={
                    "keywords": name,
                    "city": city or "",
                    "citylimit": "true" if city else "false",
                    "offset": 8,
                    "page": 1,
                    "extensions": "all",
                    "key": self.amap_key,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            if str(data.get("status")) != "1":
                print(f"⚠️  高德搜图失败: {data.get('info')}")
                return None

            pois = data.get("pois") or []
            ranked = sorted(pois, key=lambda poi: self._amap_score(poi, name), reverse=True)
            for poi in ranked:
                if self._amap_score(poi, name) <= 0:
                    continue
                photo_url = self._first_photo_url(poi)
                if photo_url:
                    print(f"🖼️  使用高德图片: {poi.get('name')} <- {name}")
                    return photo_url
        except Exception as e:
            print(f"❌ 高德搜图异常: {e}")
        return None

    def _amap_score(self, poi: Dict[str, Any], name: str) -> int:
        poi_name = str(poi.get("name") or "")
        poi_type = str(poi.get("type") or "")
        score = 0

        if poi_name == name:
            score += 50
        elif name in poi_name:
            score += 30
        elif poi_name and poi_name in name:
            score += 15
        else:
            return -1

        if any(token in poi_type for token in PREFERRED_TYPES):
            score += 20
        if any(token in poi_type for token in PENALIZED_TYPES):
            score -= 40
        if self._first_photo_url(poi):
            score += 10
        return score

    def _first_photo_url(self, poi: Dict[str, Any]) -> Optional[str]:
        photos = poi.get("photos") or []
        if not isinstance(photos, list):
            return None
        for photo in photos:
            if not isinstance(photo, dict):
                continue
            url = photo.get("url")
            if url and isinstance(url, str) and url.startswith("http"):
                return url.replace("http://", "https://", 1)
        return None

    def _from_wikipedia(self, name: str, city: str) -> Optional[str]:
        titles: List[str] = [name]
        if city:
            titles.extend([f"{name}_({city})", f"{city}{name}", f"{name} ({city})"])

        for title in titles:
            url = self._wiki_summary_image(title)
            if url:
                print(f"🖼️  使用维基图片: {title}")
                return url
        return None

    def _wiki_summary_image(self, title: str) -> Optional[str]:
        try:
            response = requests.get(
                f"https://zh.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
                headers=self.wiki_headers,
                timeout=10,
            )
            if response.status_code != 200:
                return None
            data = response.json()
            if data.get("type") == "disambiguation":
                return None
            image = data.get("originalimage") or data.get("thumbnail") or {}
            source = image.get("source")
            if source and isinstance(source, str):
                return source
        except Exception as e:
            print(f"❌ 维基搜图异常: {e}")
        return None


_photo_service = None


def get_photo_service() -> PhotoService:
    global _photo_service
    if _photo_service is None:
        _photo_service = PhotoService()
    return _photo_service
