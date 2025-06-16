# DeepWiki MCP API Changes: Workflow Failure Analysis and Fix

## Problem Summary

A GitHub Actions workflow designed to automatically generate Wiki documentation from DeepWiki has stopped working due to breaking changes in the `@regenrek/deepwiki-mcp` server API response format. The workflow fetches documentation content, processes it with Python, and generates Markdown files, but the Python parsing logic is incompatible with the new API structure.

## Old vs New API Response Structure

### Old API Response Format (What the Python script expects)

The legacy response structure used JSON-RPC 2.0 format with `result` and `content` keys:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      { "type": "text", "text": "# Page 1\n\nContent of page 1..." },
      { "type": "text", "text": "# Page 2\n\nContent of page 2..." }
    ]
  }
}
```

Or sometimes a direct string result:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "# Combined Documentation\n\nAll content here..."
}
```

### New API Response Format (Current DeepWiki MCP)

The new API uses a completely different structure with `status`, `data`, and metadata:

**For "pages" mode:**

```json
{
  "status": "ok",
  "data": [
    {
      "path": "index",
      "markdown": "# Home Page\n\nWelcome to the repository."
    },
    {
      "path": "section/page1",
      "markdown": "# First Page\n\nThis is the first page content."
    }
  ],
  "totalPages": 2,
  "totalBytes": 12000,
  "elapsedMs": 800
}
```

**For "aggregate" mode:**

```json
{
  "status": "ok",
  "data": "# Page Title\n\nPage content...\n\n---\n\n# Another Page\n\nMore content...",
  "totalPages": 5,
  "totalBytes": 25000,
  "elapsedMs": 1200
}
```

**Error responses:**

```json
{
  "status": "error",
  "code": "DOMAIN_NOT_ALLOWED",
  "message": "Only deepwiki.com domains are allowed"
}
```

**Partial success:**

```json
{
  "status": "partial",
  "data": "# Page Title\n\nPage content...",
  "errors": [
    {
      "url": "https://deepwiki.com/user/repo/page2",
      "reason": "HTTP error: 404"
    }
  ],
  "totalPages": 1,
  "totalBytes": 5000,
  "elapsedMs": 950
}
```

## Why the Current Workflow Fails

### 1. JSON Structure Mismatch

The Python script in the workflow looks for:

```python
if 'result' in data and 'content' in data['result']:
    # Process content array
elif 'result' in data and isinstance(data['result'], str):
    # Process direct string
```

But the new API returns:

- `status` instead of checking for success/failure
- `data` instead of `result`
- No `content` wrapper - data is direct

### 2. Content Processing Logic

**Old logic expects:**

```python
for item in data['result']['content']:
    if 'text' in item:
        pages_content.append(item['text'])
```

**New structure provides:**

```python
# For pages mode - array of objects with 'path' and 'markdown'
for page in data['data']:
    markdown_content = page['markdown']
    page_path = page['path']

# For aggregate mode - direct string
markdown_content = data['data']
```

### 3. Error Handling

The current script doesn't handle the new error format where `status` field indicates success/failure.

## Required Changes

### 1. Update JSON-RPC Payload (if needed)

The current payload should still work, but verify the tool name is correct:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "deepwiki_fetch",
    "arguments": {
      "url": "https://deepwiki.com/VforVitorio/F1_Strat_Manager",
      "maxDepth": 1,
      "mode": "pages"
    }
  },
  "id": 1
}
```

### 2. Update Python Parsing Logic

Replace the old parsing logic with new compatible code:

```python
def parse_deepwiki_response(data):
    """Parse the new DeepWiki MCP API response format"""
    pages_content = []

    # Check if this is the new API format
    if 'status' in data:
        if data['status'] == 'error':
            print(f"❌ API Error: {data.get('code', 'UNKNOWN')} - {data.get('message', 'No message')}")
            sys.exit(1)
        elif data['status'] in ['ok', 'partial']:
            if data['status'] == 'partial' and 'errors' in data:
                print(f"⚠️ Partial success with {len(data['errors'])} errors")
                for error in data['errors']:
                    print(f"  - {error['url']}: {error['reason']}")

            # Extract data based on mode
            if isinstance(data['data'], list):
                # Pages mode - array of page objects
                for page in data['data']:
                    if 'markdown' in page:
                        pages_content.append({
                            'content': page['markdown'],
                            'path': page.get('path', 'unknown')
                        })
            elif isinstance(data['data'], str):
                # Aggregate mode - single markdown string
                pages_content.append({
                    'content': data['data'],
                    'path': 'aggregate'
                })

            print(f"✅ Processed {data.get('totalPages', len(pages_content))} pages ({data.get('totalBytes', 0)} bytes)")
            return pages_content
        else:
            print(f"❌ Unexpected status: {data['status']}")
            sys.exit(1)

    # Fallback: Try old format for backward compatibility
    elif 'result' in data:
        print("📥 Processing legacy API format...")
        if 'content' in data['result']:
            if isinstance(data['result']['content'], list):
                for item in data['result']['content']:
                    if 'text' in item:
                        pages_content.append({
                            'content': item['text'],
                            'path': 'legacy'
                        })
            else:
                if 'text' in data['result']['content']:
                    pages_content.append({
                        'content': data['result']['content']['text'],
                        'path': 'legacy'
                    })
        elif isinstance(data['result'], str):
            pages_content.append({
                'content': data['result'],
                'path': 'legacy'
            })
        return pages_content

    else:
        print("❌ Unrecognized response format")
        print(f"Available keys: {list(data.keys())}")
        sys.exit(1)
```

### 3. Update Content Processing Loop

Replace the old loop:

```python
# OLD CODE:
for i, content in enumerate(pages_content):
    cleaned_content = clean_deepwiki_content(content)
    # ... process content

# NEW CODE:
for i, page_data in enumerate(pages_content):
    content = page_data['content']
    path = page_data['path']

    cleaned_content = clean_deepwiki_content(content)

    # Use path for better file naming if available
    if path and path != 'legacy' and path != 'aggregate':
        title = path.replace('/', ' - ').title()
        if not title:
            title = get_page_title_from_content(cleaned_content)
    else:
        title = get_page_title_from_content(cleaned_content)

    # ... continue with existing processing
```

## Complete Updated Python Script Section

Replace the Python script section in the GitHub Actions workflow with:

```python
import json
import re
import sys
import os

def parse_deepwiki_response(data):
    """Parse the new DeepWiki MCP API response format"""
    pages_content = []

    # Check if this is the new API format
    if 'status' in data:
        if data['status'] == 'error':
            print(f"❌ API Error: {data.get('code', 'UNKNOWN')} - {data.get('message', 'No message')}")
            sys.exit(1)
        elif data['status'] in ['ok', 'partial']:
            if data['status'] == 'partial' and 'errors' in data:
                print(f"⚠️ Partial success with {len(data['errors'])} errors")
                for error in data['errors']:
                    print(f"  - {error['url']}: {error['reason']}")

            # Extract data based on mode
            if isinstance(data['data'], list):
                # Pages mode - array of page objects
                for page in data['data']:
                    if 'markdown' in page:
                        pages_content.append({
                            'content': page['markdown'],
                            'path': page.get('path', 'unknown')
                        })
            elif isinstance(data['data'], str):
                # Aggregate mode - single markdown string
                pages_content.append({
                    'content': data['data'],
                    'path': 'aggregate'
                })

            print(f"✅ Processed {data.get('totalPages', len(pages_content))} pages ({data.get('totalBytes', 0)} bytes)")
            return pages_content
        else:
            print(f"❌ Unexpected status: {data['status']}")
            sys.exit(1)

    # Fallback: Try old format for backward compatibility
    elif 'result' in data:
        print("📥 Processing legacy API format...")
        if 'content' in data['result']:
            if isinstance(data['result']['content'], list):
                for item in data['result']['content']:
                    if 'text' in item:
                        pages_content.append({
                            'content': item['text'],
                            'path': 'legacy'
                        })
            else:
                if 'text' in data['result']['content']:
                    pages_content.append({
                        'content': data['result']['content']['text'],
                        'path': 'legacy'
                    })
        elif isinstance(data['result'], str):
            pages_content.append({
                'content': data['result'],
                'path': 'legacy'
            })
        return pages_content

    else:
        print("❌ Unrecognized response format")
        print(f"Available keys: {list(data.keys())}")
        sys.exit(1)

# Read and parse the JSON response
try:
    with open('docs-md/all-pages-raw.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Response structure: {list(data.keys())}")

    # Parse using new logic
    pages_content = parse_deepwiki_response(data)

    print(f"Found {len(pages_content)} content sections")

    # Rest of the existing processing logic remains the same, but update the loop:
    for i, page_data in enumerate(pages_content):
        content = page_data['content']
        path = page_data['path']

        print(f"\nProcessing content section {i+1}...")
        print(f"Content length: {len(content)} characters")
        print(f"Path: {path}")

        # Validate content
        if not content or len(str(content).strip()) == 0:
            print(f"Skipping empty content section {i+1}")
            continue

        # Ensure content is string
        if not isinstance(content, str):
            print(f"Converting content to string for section {i+1}")
            content = str(content)

        # Clean the content (existing function)
        cleaned_content = clean_deepwiki_content(content)

        if len(cleaned_content.strip()) < 50:
            print(f"Skipping short content section {i+1}")
            continue

        # Enhanced title extraction using path
        if path and path not in ['legacy', 'aggregate', 'unknown']:
            # Convert path to title (e.g., "section/page1" -> "Section - Page1")
            title = path.replace('/', ' - ').replace('-', ' ').title()
            # Clean up the title
            title = re.sub(r'\s+', ' ', title).strip()
            if not title:
                title = get_page_title_from_content(cleaned_content)
        else:
            title = get_page_title_from_content(cleaned_content)

        # Rest of existing logic continues unchanged...
        # (categorization, file writing, etc.)
```

## Testing the Fix

1. **Deploy the updated workflow**
2. **Monitor the logs** for the new parsing messages
3. **Verify file generation** with `ls -la docs-md/`
4. **Check content quality** with `head -30 docs-md/*.md`

## Backward Compatibility

The updated code maintains backward compatibility by:

- First checking for new API format (`status` field)
- Falling back to old format (`result` field) if new format not detected
- Providing clear logging to indicate which format is being processed

This ensures the workflow will work with both old and new versions of the DeepWiki MCP server.
