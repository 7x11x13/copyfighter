# copyfighter
This project is how I semi-automatically process and submit disputes against fake copyright claims on my YouTube channel.

## How it works
1. Video claims are fetched using the [internal YouTube API](https://github.com/7x11x13/youtube-up/commit/48f52c78727dc86a1e8c5625bb1883c1e0777b72), using cookies relayed by my [cookie-relay](https://github.com/7x11x13/cookie-relay) instance
3. Claims are scored on their legitimacy by an LLM through Cloudflare AI (this is prob not that useful but I just wanted to try it out)
4. Claims are confirmed fake/real by me via Discord. Queue is sorted by AI-given score to prioritize higher scored claims
5. Claims are disputed using the internal YouTube API