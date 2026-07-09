# Proxy Configuration for NBA API Calls

This document explains how to set up and use proxy configuration for NBA API calls to avoid IP blocking from AWS instances.

## Overview

We use [swar/nba_api](https://github.com/swar/nba_api) for `stats.nba.com`. Per their docs, every endpoint accepts:

```python
CommonPlayerInfo(player_id=2544, proxy='http://user:pass@host:port', headers=STATS_HEADERS, timeout=100)
```

Important: pass nba_api's `STATS_HEADERS` (includes `x-nba-stats-token` / `x-nba-stats-origin`). Custom headers that omit those often hang or time out.

The NBA API may also block datacenter / AWS IP ranges. To work around this, we've implemented a proxy configuration system that allows you to:

1. Use a single proxy server
2. Rotate between multiple proxy servers
3. Customize request headers to appear more like a browser
4. Automatically detect when running on AWS vs. locally

## Configuration

### Environment Variables

Set the following environment variables in your AWS environment:

```
PROXY_ENABLED=true
FORCE_LOCAL=false
FORCE_PROXY=false
```

- `PROXY_ENABLED`: Set to "true" to enable proxy usage, "false" to disable
- `FORCE_LOCAL`: Set to "true" to force direct connections (no proxy) even when running on AWS
- `FORCE_PROXY`: Set to "true" to force proxy usage even when running locally

The system will automatically detect if you're running on AWS and enable proxies accordingly, but you can override this behavior with these environment variables.

### Decodo / SmartProxy Configuration

Set these in `.env` (never commit real credentials):

```
SMARTPROXY_USERNAME=user-your_username
SMARTPROXY_PASSWORD=your_password
SMARTPROXY_HOST=gate.decodo.com
SMARTPROXY_PORTS=7000
SMARTPROXY_SCHEME=http
FORCE_LOCAL=false
```

Notes:
- Use `SMARTPROXY_SCHEME=http` (not `https`) for the proxy URL. `https://user:pass@gate...` commonly fails with `RemoteDisconnected`.
- Decodo usernames must start with `user-`. The app auto-prefixes if missing.
- Residential rotating endpoint is usually port `7000`. Sticky ports `10001-10010` work only if your plan exposes them.
- Keep `FORCE_LOCAL=false` so `--proxy` can enable proxies.

## Usage

The proxy configuration is automatically applied to all NBA API calls through the `api_utils.py` module. You don't need to modify your code to use proxies - just set the environment variables.

### Testing Proxy Configuration

Run the test script to verify your proxy configuration:

```bash
# Test with automatic detection (proxy on AWS, direct on local)
python scripts/test_proxy.py

# Force proxy usage even when running locally
python scripts/test_proxy.py --proxy

# Force direct connection even when running on AWS
python scripts/test_proxy.py --local
```

This will test the connection to the NBA API using your proxy configuration and display the results.

### Local Development

When developing locally, the system will automatically detect that you're not on AWS and disable proxies. This allows you to:

1. Develop and test without using up your proxy bandwidth
2. Avoid potential latency issues introduced by proxies
3. Debug API calls more easily

If you want to test proxy functionality locally, you can use the `--proxy` flag with the test script or set `FORCE_PROXY=true` in your environment.

## Troubleshooting

If you encounter issues with the proxy configuration:

1. **Connection timeouts**: Increase the timeout value in `get_api_config()` in `api_utils.py`
2. **Proxy authentication failures**: Double-check your proxy credentials
3. **Proxy blocking**: Some proxies may be blocked by the NBA API - try a different proxy
4. **Rate limiting**: Adjust the `RateLimiter` parameters in `config_utils.py`

## Implementation Details

The proxy configuration is implemented in the following files:

- `app/utils/config_utils.py`: Contains the proxy configuration and helper functions
- `app/utils/fetch/api_utils.py`: Provides utilities for using proxies with NBA API calls
- `scripts/test_proxy.py`: Test script for verifying proxy configuration

The implementation uses the built-in proxy support in the NBA API library, which accepts proxy URLs and custom headers as parameters. 