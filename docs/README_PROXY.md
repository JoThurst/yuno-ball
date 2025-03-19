# NBA API Proxy Configuration

This README provides instructions on how to use the proxy configuration in your NBA Sports Analytics application.

## Overview

The NBA API may block requests coming from AWS IP ranges. To work around this, we've implemented a proxy configuration system that allows you to:

1. Use SmartProxy to mask your AWS IP addresses
2. Rotate between multiple proxy endpoints
3. Customize request headers to appear more like a browser
4. Automatically detect when running on AWS vs. locally

## Quick Start

### Testing the Proxy Configuration

1. Run the test script to verify your proxy configuration:

```bash
# Windows
scripts\test_proxy.bat

# Linux/Mac
python scripts/test_proxy.py
```

2. Test with forced proxy usage (even when running locally):

```bash
# Windows
scripts\test_proxy.bat --proxy

# Linux/Mac
python scripts/test_proxy.py --proxy
```

3. Test with forced direct connection (even when running on AWS):

```bash
# Windows
scripts\test_proxy.bat --local

# Linux/Mac
python scripts/test_proxy.py --local
```

4. Test the SmartProxy configuration directly:

```bash
# Windows
scripts\test_smartproxy.bat

# Linux/Mac
python scripts/test_smartproxy.py
```

### Running the Application with Proxy Support

You can run the application with proxy support using command-line flags:

```bash
# Run with proxy support (even when running locally)
python run.py --proxy

# Run with direct connection (even when running on AWS)
python run.py --local

# Run with cache warming and proxy support
python run.py --warm-cache --proxy
```

### Running Ingestion Scripts with Proxy Support

You can run the ingestion scripts with proxy support using command-line flags:

```bash
# Run daily ingestion with proxy support
python daily_ingest.py --proxy

# Run one-time ingestion with proxy support
python ingest_data.py --proxy

# Run with direct connection
python daily_ingest.py --local
```

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

### AWS Setup

1. Add these environment variables to your AWS environment:

```
PROXY_ENABLED=true
```

2. Make sure your application has outbound access to the SmartProxy servers.

## Local Development

When developing locally, the system will automatically detect that you're not on AWS and disable proxies. This allows you to:

1. Develop and test without using up your proxy bandwidth
2. Avoid potential latency issues introduced by proxies
3. Debug API calls more easily

If you want to test proxy functionality locally, you can use the `--proxy` flag with the test script or set `FORCE_PROXY=true` in your environment.

## Implementation Details

The proxy configuration is implemented in the following files:

- `app/utils/config_utils.py`: Contains the proxy configuration and helper functions
- `app/utils/fetch/api_utils.py`: Provides utilities for using proxies with NBA API calls
- `scripts/test_proxy.py`: Test script for verifying proxy configuration
- `scripts/test_smartproxy.py`: Test script for testing the SmartProxy configuration directly

### Finding and Updating API Calls

To find NBA API calls that need to be updated to use the proxy configuration, run:

```bash
# Windows
scripts\update_api_calls.bat

# Linux/Mac
python scripts/update_remaining_api_calls.py
```

This will scan your codebase for NBA API calls and provide instructions on how to update them.

## Troubleshooting

If you encounter issues with the proxy configuration:

1. **Connection timeouts**: Increase the timeout value in `get_api_config()` in `api_utils.py`
2. **Proxy authentication failures**: Double-check your proxy credentials
3. **Proxy blocking**: Some proxies may be blocked by the NBA API - try a different proxy
4. **Rate limiting**: Adjust the `RateLimiter` parameters in `config_utils.py`

## SmartProxy Information

The application is pre-configured with SmartProxy credentials:

- Username: `user-sppc24ewsr-sessionduration-5`
- Password: `jnD6WnupJ4Zv21i_ai`
- Host: `gate.smartproxy.com`
- Ports: 10001-10010

These credentials are used to build a list of proxy URLs that the application will rotate between.

For more information about SmartProxy, visit [SmartProxy's website](https://smartproxy.com/). 