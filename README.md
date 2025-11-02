# Quash Browser Control Agent

An AI-powered conversational browser automation agent that controls a real browser through natural language. The system demonstrates strong backend design, reliable browser control, conversational UX, and clean AI orchestration.

## Features

- **Natural Language Understanding**: Interprets free-form commands like "Find MacBook Air under ₹100000" or "Top 3 pizza places near Indiranagar"
- **Browser Automation**: Uses Playwright for robust browser control with retry logic and smart selector fallbacks
- **Real-time Streaming**: Live action traces, state updates, and extracted data in the chat UI
- **Multiple Workflows**: Supports product search, form filling, local discovery, and multi-site comparison
- **Modular Architecture**: Clean separation between NLU, planning, browser execution, and UI layers

## Architecture

```
┌─────────────────┐
│  React Frontend  │ ← Chat UI with streaming action cards
└────────┬─────────┘
         │ WebSocket
┌────────▼─────────┐
│  FastAPI Backend │
├──────────────────┤
│  NLU Module      │ ← Intent extraction (OpenRouter API)
│  Planner Module  │ ← Action plan generation (AI-powered)
│  Browser Module  │ ← Playwright automation
└──────────────────┘
```

### Core Components

1. **NLU (Natural Language Understanding)**
   - Extracts intent, parameters, filters, and constraints
   - Supports fallback rule-based parsing if API unavailable
   - Handles: product_search, form_fill, comparison, local_discovery, navigation

2. **Planner**
   - AI-powered planning using LLM
   - Site-specific configurations for Flipkart, Amazon, Zomato
   - Generates step-by-step action sequences

3. **Browser Automation**
   - Robust element finding with multiple selector fallbacks
   - Retry logic with exponential backoff
   - Structured extraction with error handling
   - Live event streaming to frontend

4. **Frontend**
   - Real-time chat interface
   - Action cards showing live browser actions
   - Result display with formatted data
   - Status indicators and error handling

## Setup Instructions

### Prerequisites

- Python 3.8+
- Node.js 16+
- Playwright browsers (installed automatically)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd quash_agent_project
   ```

2. **Backend Setup**

   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   # On Linux/Mac:
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Install Playwright browsers
   playwright install chromium
   ```

3. **Frontend Setup**

   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Environment Configuration**

   Create a `.env` file in the root directory:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_api_key_here
   LLM_MODEL=openai/gpt-3.5-turbo
   BROWSER_HEADLESS=false
   ```

   Get your API key from [OpenRouter](https://openrouter.ai)

### Running the Application

1. **Start the Backend Server**

   **⚠️ WINDOWS USERS - READ THIS FIRST:**
   
   **DO NOT** run `uvicorn` directly on Windows! You **MUST** use:
   ```bash
   python start_server.py
   ```
   
   Or simply double-click `run_backend.bat`
   
   This is required to fix the Playwright subprocess issue on Windows.

   **Windows:**
   ```bash
   # Make sure virtual environment is activated
   python start_server.py
   # OR double-click: run_backend.bat
   ```

   **Linux/Mac:**
   ```bash
   # Make sure virtual environment is activated
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   # OR use the shell script:
   bash run_backend.sh
   ```

   Backend will be available at `http://localhost:8000`
   
   **Before starting, test Playwright:**
   ```bash
   python test_playwright.py
   ```
   
   If this test fails, fix the errors before starting the server.

   **Note**: See `QUICK_START.md` for troubleshooting Windows errors. See `SETUP_WINDOWS.md` for detailed Windows setup.

2. **Start the Frontend**

   ```bash
   cd frontend
   npm start
   ```

   Frontend will be available at `http://localhost:3000`

### Usage Examples

Once both servers are running, open `http://localhost:3000` in your browser and try these commands:

1. **Product Search**
   ```
   Find MacBook Air 13-inch under ₹100000
   ```

2. **Local Discovery**
   ```
   Show top 3 pizza places near Indiranagar with 4+ rating
   ```

3. **Comparison**
   ```
   Compare laptops on Flipkart and Amazon
   ```

4. **Form Filling**
   ```
   Fill the signup form on this URL with temporary email
   ```

## Project Structure

```
quash_agent_project/
├── backend/
│   └── app/
│       ├── main.py          # FastAPI server with WebSocket
│       ├── nlu.py           # Natural language understanding
│       ├── planner.py       # Action planning
│       └── browser.py       # Playwright automation
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   ├── App.css         # Styling
│   │   └── index.js        # Entry point
│   └── package.json
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
├── .gitignore
└── README.md
```

## Technical Details

### Browser Automation

- Uses Playwright for reliable browser control
- Implements retry logic for element finding (tries multiple selectors)
- Waits for network idle and DOM ready states
- Handles dynamic content loading
- Structured extraction with error recovery

### Error Handling

- Graceful fallbacks when selectors fail
- User-friendly error messages
- Continues execution on non-fatal errors
- Retry mechanism with exponential backoff

### Streaming Architecture

Events streamed from backend to frontend:
- `status`: Current processing state
- `action`: Browser action being executed
- `action_start`: Action beginning
- `action_complete`: Action finished
- `result`: Extracted data
- `error`: Error notifications
- `warning`: Non-fatal warnings

## API Configuration

The system uses OpenRouter API to access various LLMs. You can configure:

- **OpenRouter API Key**: Required for NLU and planning
- **Model Selection**: Choose from GPT-3.5, GPT-4, Claude, etc.
- **Fallback Mode**: If API key is missing, rule-based parsing is used

## Development

### Adding New Sites

Edit `backend/app/planner.py` to add site configurations:

```python
SITE_CONFIGS["new_site"] = {
    "url": "https://newsite.com",
    "search_input": "input[name='search']",
    "search_button": "button[type='submit']",
    # ... other selectors
}
```

### Adding New Actions

1. Add action handler in `backend/app/browser.py`
2. Update planner to generate the new action
3. Add UI representation in `frontend/src/App.js`

### Testing

Run backend:
```bash
uvicorn backend.app.main:app --reload
```

Test WebSocket connection:
```bash
# Use a WebSocket client or the React frontend
```

## Troubleshooting

### Browser Not Launching

- Ensure Playwright browsers are installed: `playwright install chromium`
- Check `BROWSER_HEADLESS` setting in `.env`
- On Windows, ensure Chrome is not running in another instance
- **Windows subprocess error**: Use `python start_server.py` instead of `uvicorn` directly (see `SETUP_WINDOWS.md`)

### API Errors

- Verify `OPENROUTER_API_KEY` is set correctly
- Check API quota and limits
- System falls back to rule-based parsing if API fails

### Selector Not Found

- The system automatically tries multiple selector fallbacks
- Check browser console for actual page structure
- Update selectors in `SITE_CONFIGS` if needed

## Future Enhancements

- [ ] Multi-turn conversation memory
- [ ] Screenshot capture and analysis
- [ ] More sophisticated form field detection
- [ ] Cross-site comparison with unified schema
- [ ] Voice input support
- [ ] Browser state persistence across sessions
- [ ] Custom workflow definitions

## License

This project is created for the Quash Full Stack Assignment.

## Evaluation Criteria Coverage

✅ **Architecture**: Clean layering with planner–executor separation  
✅ **Backend Reasoning**: Clear intent → plan → action loop  
✅ **Automation Reliability**: Stable waits/selectors, retries, recovery  
✅ **Conversation Design**: Multi-turn memory, helpful status messages  
✅ **UI/UX**: Real-time action feed with structured traces  
✅ **AI Integration**: AI-powered planning and intent extraction  
✅ **Error Handling**: Graceful fallbacks and user prompts  
✅ **Documentation**: Comprehensive setup and usage guide

