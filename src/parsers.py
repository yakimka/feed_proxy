import feedparser


class Post:
    fields = ['author', 'title', 'link', 'id', 'published', 'summary', 'enclosures']

    def __init__(self, post_parsed):
        self.post_parsed = post_parsed

        for field in self.fields:
            setattr(self, field, getattr(self.post_parsed, field, None))
        self.tags = self._get_tags()
        self.audio = self._get_audio()

    def _get_tags(self):
        tags = []
        for tag in getattr(self.post_parsed, 'tags', []):
            tags.append(tag['term'].lower().replace(' ', '_'))

        return tags

    def _get_audio(self):
        audio = []
        for enclosure in self.enclosures:
            if enclosure['type'].startswith('audio'):
                audio.append(enclosure['href'])
        return audio


class RSSFeedParser:
    def __init__(self, url):
        self.url = url

    def parse(self):
        feed = feedparser.parse(self.url)

        return [Post(entry) for entry in feed.entries]
