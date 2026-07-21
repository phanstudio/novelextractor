import time
from urllib.parse import urljoin, urlparse
import cloudscraper
from bs4 import BeautifulSoup, SoupStrainer
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import re

# Constants
BASE_URL = "https://freewebnovel.com"
MIN_INTERVAL = 3.4  # seconds between calls

CATEGORIES = [
    "Action", "Adult", "Adventure", "Comedy", "Drama", "Eastern", "Ecchi",
    "Fantasy", "Game", "Gender+Bender", "Harem", "Historical", "Horror",
    "Josei", "Martial+Arts", "Mature", "Mecha", "Mystery", "Psychological",
    "Reincarnation", "Romance", "School+Life", "Sci-fi", "Seinen", "Shoujo",
    "Shounen+Ai", "Shounen", "Slice+of+Life", "Smut", "Sports",
    "Supernatural", "Tragedy", "Wuxia", "Xianxia", "Xuanhuan", "Yaoi"
]

# Enums and Data Classes
class NovelStatus(Enum):
    ONGOING = "Ongoing"
    ON_HIATUS = "On Hiatus"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"
    UNKNOWN = "Unknown"

class ParserState(Enum):
    IDLE = 0
    INFO = 1
    COVER = 2
    AUTHOR = 3
    GENRES = 4
    STATUS = 5
    SUMMARY = 6
    NOVEL_NAME = 7

@dataclass
class Novel:
    path: str
    name: Optional[str] = None
    cover: Optional[str] = None
    author: Optional[str] = None
    genres: Optional[List[str]] = None
    status: NovelStatus = NovelStatus.UNKNOWN
    summary: Optional[str] = None
    last_chapter: Optional[str] = None

# Utility Functions
class RequestThrottler:
    """Centralized request throttling to avoid hammering the server"""
    
    def __init__(self, min_interval: float = MIN_INTERVAL):
        self.min_interval = min_interval
        self.last_request_ts = 0.0
    
    def throttle(self):
        """Ensure minimum interval between requests"""
        now = time.time()
        elapsed = now - self.last_request_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_ts = time.time()

def extract_novel_path(href: str, base_url: str = BASE_URL) -> str:
    """Extract novel path from href, handling URL joining properly"""
    if not href:
        return ""
    
    full_url = urljoin(base_url, href)
    parsed = urlparse(full_url)
    path = parsed.path.lstrip('/')
    return path

def parse_novel_list_section(soup: BeautifulSoup, base_url: str = BASE_URL) -> List[Dict[str, Optional[str]]]:
    """
    Common function to parse novel list sections from search/category pages.
    Eliminates duplicated parsing logic.
    """
    novels = []
    
    for row in soup.find_all("div", class_="li-row"):
        # Extract cover image
        pic_div = row.find("div", class_="pic")
        cover_url = None
        if pic_div:
            img_tag = pic_div.find("img")
            if img_tag and img_tag.get("src"):
                cover_url = urljoin(base_url, img_tag["src"])
        
        # Extract title and path
        title_tag = row.find("h3", class_="tit")
        name = None
        path = None
        if title_tag:
            a_tag = title_tag.find("a")
            if a_tag:
                name = a_tag.get_text(strip=True) or None
                href = a_tag.get("href", "")
                path = extract_novel_path(href, base_url)
        
        novels.append({
            "name": name,
            "path": path,
            "cover": cover_url
        })
    
    return novels

# Main Classes
class FreeWebNovelSearcher:
    """Search for novels on FreeWebNovel"""
    
    def __init__(self, throttler: RequestThrottler, scraper: cloudscraper.CloudScraper):
        self.site = BASE_URL
        self.search_url = f"{self.site}/search"
        self.search_key = "searchkey"
        self.throttler = throttler
        self.scraper = scraper

    def search(self, query: str) -> List[Dict[str, Optional[str]]]:
        """
        Search for novels by query string.
        
        Returns:
            List of dicts with keys: name, path, cover
        """
        self.throttler.throttle()
        
        payload = {self.search_key: query}
        resp = self.scraper.post(self.search_url, data=payload)
        
        resp.raise_for_status()
        html = resp.text
        
        # Parse only the search results section
        # strainer = SoupStrainer("div", {"class": "ul-list1 ul-list1-2 ss-custom"})
        strainer = SoupStrainer("div", class_=["ul-list1"])
        soup = BeautifulSoup(html, "html.parser", parse_only=strainer)
        print(soup)

        strainer2 = SoupStrainer("div", class_=["ul-list1", "ul-list1-2", "ss-custom"])
        soup2 = BeautifulSoup(html, "html.parser", parse_only=strainer)
        print(soup2)
        
        return parse_novel_list_section(soup, self.site)

class FreeWebNovelCategory:
    """Browse novels by category/genre"""
    
    def __init__(self, throttler: RequestThrottler, scraper: cloudscraper.CloudScraper):
        self.throttler = throttler
        self.scraper = scraper
        

    def list_categories(self) -> List[str]:
        """Return list of all available genre categories"""
        return CATEGORIES.copy()

    def fetch_category_page(self, genre_slug: str, page: int = 1) -> List[Dict[str, Optional[str]]]:
        """
        Fetch novels from a specific genre category page.
        
        Args:
            genre_slug: Genre name (e.g., "Fantasy", "Action")
            page: Page number (default: 1)
            
        Returns:
            List of dicts with keys: name, path, cover
        """
        self.throttler.throttle()
        
        genre_url = f"{BASE_URL}/genre/{genre_slug}"
        params = {"page": page}
        resp = self.scraper.get(genre_url, params=params)
        resp.raise_for_status()
        
        # Parse only the novels list section
        strainer = SoupStrainer("div", {"class": "ul-list1 ul-list1-2 ss-custom"})
        soup = BeautifulSoup(resp.text, "html.parser", parse_only=strainer)
        
        return parse_novel_list_section(soup, BASE_URL)

class NovelInfoParser:
    """Parse detailed information from novel pages"""
    
    def __init__(self, throttler: RequestThrottler, scraper: cloudscraper.CloudScraper, base_url: str = BASE_URL, options: Dict[str, Any] = None):
        self.base_url = base_url.rstrip('/')
        self.options = options or {}
        self.throttler = throttler
        self.scraper = scraper
        
    def get_novel_info(self, novel_path: str) -> Novel:
        """
        Extract detailed novel information from a novel page.
        
        Args:
            novel_path: Path to novel (e.g., "novel/some-title")
            
        Returns:
            Novel object with detailed information
        """
        self.throttler.throttle()
        
        url = f"{self.base_url}/{novel_path.lstrip('/')}"
        
        response = self.scraper.get(url)
        response.raise_for_status()
        
        novel = self._parse_novel_html(response.text, novel_path)
        
        # Get last chapter info
        try:
            novel.last_chapter = self._extract_last_chapter(response.text)
        except Exception as e:
            print(f"Warning: Could not extract last chapter: {e}")
            novel.last_chapter = None
            
        return novel
    
    def _parse_novel_html(self, html: str, novel_path: str) -> Novel:
        """Parse novel HTML using state machine approach"""
        soup = BeautifulSoup(html, 'html.parser')
        novel = Novel(path=novel_path)
        
        # Data collectors
        summary_parts = []
        author_parts = []
        
        # State tracking
        state_stack = [ParserState.IDLE]
        
        def get_current_state():
            return state_stack[-1]
        
        # Parse all elements
        for element in soup.find_all(True):
            tag_name = element.name
            attrs = element.attrs
            current_state = get_current_state()
            
            # Handle opening tags
            self._handle_opening_tag(
                tag_name, attrs, current_state, state_stack,
                novel, summary_parts
            )
            
            # Handle text content
            if element.string and element.string.strip():
                self._handle_text_content(
                    element.string, get_current_state(), novel,
                    summary_parts, author_parts
                )
        
        # Process collected data
        self._process_collected_data(novel, summary_parts, author_parts)
        
        return novel
    
    def _handle_opening_tag(self, tag_name, attrs, current_state, state_stack,
                          novel, summary_parts):
        """Handle opening HTML tags based on parser state"""
        class_name = attrs.get('class', [])
        if isinstance(class_name, list):
            class_name = ' '.join(class_name)
        
        if tag_name == 'div':
            if 'books' in class_name or 'm-imgtxt' in class_name:
                state_stack.append(ParserState.COVER)
            elif 'inner' in class_name or 'desc-text' in class_name:
                if current_state == ParserState.COVER:
                    state_stack.pop()
                state_stack.append(ParserState.SUMMARY)
            elif 'info' in class_name:
                state_stack.append(ParserState.INFO)
        
        elif tag_name == 'img' and current_state == ParserState.COVER:
            img_src = (
                attrs.get('src') or 
                attrs.get('data-cfsrc') or 
                attrs.get('data-src')
            )
            title = attrs.get('title')
            
            if img_src:
                novel.cover = urljoin(self.base_url, img_src)
            if title and not novel.name:  # Avoid redundant setting
                novel.name = title
        
        elif tag_name == 'h3' and current_state == ParserState.COVER:
            state_stack.append(ParserState.NOVEL_NAME)
        
        elif tag_name == 'span' and current_state == ParserState.COVER:
            span_title = attrs.get('title')
            if span_title:
                state_map = {
                    'Genre': ParserState.GENRES,
                    'Author': ParserState.AUTHOR,
                    'Status': ParserState.STATUS
                }
                if span_title in state_map:
                    state_stack.append(state_map[span_title])
        
        elif tag_name == 'br' and current_state == ParserState.SUMMARY:
            summary_parts.append('\n')
        
        elif tag_name == 'ul' and 'info-meta' in class_name:
            state_stack.append(ParserState.INFO)
    
    def _handle_text_content(self, text, current_state, novel,
                           summary_parts, author_parts):
        """Handle text content based on parser state"""
        trimmed_text = text.strip()
        if not trimmed_text:
            return
            
        if current_state == ParserState.NOVEL_NAME:
            if novel.name:
                novel.name += text
            else:
                novel.name = text
        elif current_state == ParserState.SUMMARY:
            summary_parts.append(text)
        elif current_state == ParserState.AUTHOR:
            author_parts.append(text)
    
    def _process_collected_data(self, novel, summary_parts, author_parts): # i have access to summary and chapters
        """Process and assign collected data to novel object"""
        author, genres, status = self._extract_metadata(author_parts)
        novel.author = author
        novel.genres = genres
        novel.status = self._parse_status(status) if status else NovelStatus.UNKNOWN
        
        # Clean up summary
        if summary_parts:
            novel.summary, chapters = self.extract_summary_and_chapters('\n\n'.join(summary_parts).strip())
    
    def _extract_metadata(self, items):
        """Extract author, genres, and status from text items"""
        items = [item.lower().strip() for item in items if item.strip()]
        
        social_tokens = {"facebook", "twitter", "whatsapp", "pinterest"}
        known_statuses = {"ongoing", "completed", "hiatus", "cancelled"}
        known_genres = {i.lower() for i in CATEGORIES}
        
        author = None
        genres = []
        status = None
        
        for item in items:
            if item in social_tokens or " / 5" in item:
                continue
            elif item in known_statuses:
                status = item.capitalize()
            elif item in known_genres:
                formatted_genre = item.replace('+', ' ').title()
                if formatted_genre not in genres:
                    genres.append(formatted_genre)
            elif not author and len(item) > 1:  # Avoid single character authors
                author = item.title()
        
        return author, genres, status
    
    def _parse_status(self, status_text: str) -> NovelStatus:
        """Convert status text to NovelStatus enum"""
        if not status_text:
            return NovelStatus.UNKNOWN
            
        status_lower = status_text.lower()
        status_map = {
            'ongoing': NovelStatus.ONGOING,
            'hiatus': NovelStatus.ON_HIATUS,
            'dropped': NovelStatus.CANCELLED,
            'cancelled': NovelStatus.CANCELLED,
            'completed': NovelStatus.COMPLETED
        }
        return status_map.get(status_lower, NovelStatus.UNKNOWN)
    
    def _extract_last_chapter(self, response_text: str) -> Optional[str]:
        """Extract the last chapter number from novel page"""
        soup = BeautifulSoup(response_text, "html.parser")
        
        # Find the latest chapter link
        link_element = soup.select_one(
            "body > div.main > div > div > div.col-content > div.m-newest1 > ul > li:nth-child(1) > a"
        )
        
        if link_element:
            href = link_element.get('href')
            if href:
                # Extract chapter number from URL
                parts = href.split("/")
                if parts:
                    return parts[-1].split("-")[-1]
        
        return None

    def extract_summary_and_chapters(self, text):
        # Extract summary: stop at "Add to Library" or "[ Updated"
        summary_match = re.search(r"^(.*?)(?:Add to Library|\[ Updated)", text, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        # Extract chapters: all lines starting with "Chapter" followed by a number
        chapter_pattern = re.compile(r"Chapter\s+(\d+)[\s:-]+(.+)")
        chapters = [
            {"number": int(num), "title": title.strip()}
            for num, title in chapter_pattern.findall(text)
        ]

        return summary, chapters
    
    def update(self, novel_path: str) -> Optional[str]:
        """
        Update and get the latest chapter for a novel.
        
        Args:
            novel_path: Path to novel (e.g., "novel/some-title")
            
        Returns:
            Latest chapter number or None if not found
        """
        self.throttler.throttle()
        
        # Handle both full paths and novel slugs
        if novel_path.startswith('novel/'):
            novel_slug = novel_path.replace('novel/', '')
        else:
            novel_slug = novel_path
            
        url = f"{self.base_url}/novel/{novel_slug}"
        
        try:
            response = self.scraper.get(url)
            response.raise_for_status()
            return self._extract_last_chapter(response.text)
        except Exception as e:
            print(f"Error updating novel {novel_path}: {e}")
            return None

class NovelChapterextractor:
    """Parse detailed information from novel pages"""

    def __init__(self, scraper: cloudscraper.CloudScraper):
        self.base_url = BASE_URL.rstrip('/')
        self.scraper = scraper

    def extract_chapter(self, novel, num):
        url = f"https://freewebnovel.com/novel/{novel}/chapter-{num}"
        try:
            response = self.scraper.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = soup.find_all('p')
            text = "\n".join(p.text.strip() for p in paragraphs)
            
            return text
        except:
            return None

# Main API Class
class FreeWebNovelAPI:
    """Main API class that combines all functionality"""
    
    def __init__(self, sleep_interval: float = MIN_INTERVAL):
        # Single throttler shared across all components
        self.throttler = RequestThrottler(sleep_interval)

        self.scraper = cloudscraper.create_scraper()  # Create once here
        self.searcher = FreeWebNovelSearcher(self.throttler, self.scraper)
        self.category_browser = FreeWebNovelCategory(self.throttler, self.scraper)
        self.info_parser = NovelInfoParser(self.throttler, self.scraper)
        self.chapter_extractor = NovelChapterextractor(self.scraper)
        
    def search(self, query: str) -> List[Dict[str, Optional[str]]]:
        """Search for novels by query"""
        return self.searcher.search(query)
    
    def get_categories(self) -> List[str]:
        """Get list of available categories"""
        return self.category_browser.list_categories()
    
    def browse_category(self, genre: str, page: int = 1) -> List[Dict[str, Optional[str]]]:
        """Browse novels by category"""
        return self.category_browser.fetch_category_page(genre, page)
    
    def get_novel_info(self, novel_path: str) -> Novel:
        """Get detailed novel information"""
        return self.info_parser.get_novel_info(novel_path)
    
    def update_novel(self, novel_path: str) -> Optional[str]:
        """Get latest chapter for a novel"""
        return self.info_parser.update(novel_path)
    
    def extract_chapter(self, novel_name:str, chapter_num:int) -> Optional[str]:
        """Get latest chapter for a novel"""
        return self.chapter_extractor.extract_chapter(novel_name, chapter_num)

def main():
    """Example usage of the FreeWebNovel API"""
    api = FreeWebNovelAPI()
    
    # Search for novels
    print("=== Search Results ===")
    search_results = api.search("death")
    for novel in search_results[:3]:  # Show first 3 results
        print(f"Title: {novel['name']}")
        print(f"Path: {novel['path']}")
        print()
    
    # Browse by category
    print("=== Fantasy Novels ===")
    fantasy_novels = api.browse_category("Fantasy", page=1)
    for novel in fantasy_novels[:3]:  # Show first 3 results
        print(f"Title: {novel['name']}")
        print(f"Path: {novel['path']}")
        print()
    
    # Get detailed novel info
    if search_results:
        print("=== Detailed Novel Info ===")
        try:
            novel_info = api.get_novel_info(search_results[0]['path'])
            print(f"Title: {novel_info.name}")
            print(f"Author: {novel_info.author}")
            print(f"Status: {novel_info.status.value}")
            print(f"Genres: {novel_info.genres}")
            print(f"Last Chapter: {novel_info.last_chapter}")
            print(f"Summary: {novel_info.summary[:200] if novel_info.summary else 'No summary'}...")
            
            # Test update functionality
            print(f"\n=== Update Test ===")
            latest_chapter = api.update_novel(search_results[0]['path'])
            print(f"Latest chapter: {latest_chapter}")
            
        except Exception as e:
            print(f"Error getting novel info: {e}")

if __name__ == "__main__":
    main()
