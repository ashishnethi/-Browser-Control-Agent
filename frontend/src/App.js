import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [currentStatus, setCurrentStatus] = useState('ready');
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const connectWebSocket = () => {
    const backendHost = process.env.REACT_APP_BACKEND_URL || 
                        (window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host);
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${backendHost}/ws/chat`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      setIsConnected(true);
      addMessage('system', 'Connected to agent', 'success');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (e) {
        console.error('Error parsing message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      addMessage('system', 'Connection error', 'error');
    };

    ws.onclose = () => {
      setIsConnected(false);
      addMessage('system', 'Disconnected. Reconnecting...', 'warning');
      setTimeout(connectWebSocket, 3000);
    };

    wsRef.current = ws;
  };

  const handleWebSocketMessage = (data) => {
    const { type } = data;

    switch (type) {
      case 'user_message':
        addMessage('user', data.content);
        break;

      case 'status':
        setCurrentStatus(data.status);
        addMessage('agent', data.message, 'status');
        break;

      case 'intent':
        addMessage('agent', `Intent detected: ${data.data.intent}`, 'info');
        break;

      case 'plan':
        addMessage('agent', `Plan generated: ${data.step_count} steps`, 'info', {
          type: 'plan',
          plan: data.plan
        });
        break;

      case 'action_start':
        addMessage('agent', `Starting: ${data.action} (${data.step}/${data.total_steps})`, 'action', data);
        break;

      case 'action':
        addMessage('agent', data.message || `${data.action}: ${data.target || ''}`, 'action', data);
        break;

      case 'action_complete':
        updateLastActionMessage(data.action, 'completed');
        break;

      case 'warning':
        addMessage('agent', data.message, 'warning', data);
        break;

      case 'error':
        addMessage('agent', data.message, 'error', data);
        setCurrentStatus('error');
        break;

      case 'result':
        const resultCount = data.count || (data.data ? data.data.length : 0);
        addMessage('agent', `Found ${resultCount} results`, 'result', data);
        break;

      default:
        if (data.message || data.content) {
          addMessage('agent', data.message || data.content, 'info', data);
        }
    }
  };

  const addMessage = (sender, text, variant = 'info', data = null) => {
    const message = {
      id: Date.now() + Math.random(),
      sender,
      text,
      variant,
      timestamp: new Date(),
      data
    };
    setMessages(prev => [...prev, message]);
  };

  const updateLastActionMessage = (action, status) => {
    setMessages(prev => {
      const newMessages = [...prev];
      // Find last matching message (reverse iteration for compatibility)
      let lastActionIdx = -1;
      for (let i = newMessages.length - 1; i >= 0; i--) {
        if (newMessages[i].data?.action === action && newMessages[i].variant === 'action') {
          lastActionIdx = i;
          break;
        }
      }
      if (lastActionIdx >= 0) {
        newMessages[lastActionIdx] = {
          ...newMessages[lastActionIdx],
          status
        };
      }
      return newMessages;
    });
  };

  const handleSend = () => {
    if (!inputValue.trim() || !isConnected) return;

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(inputValue);
      setInputValue('');
      setCurrentStatus('processing');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🤖 Quash Browser Agent</h1>
        <div className="status-indicator">
          <span className={`status-dot ${currentStatus}`}></span>
          <span className="status-text">{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </header>

      <div className="chat-container">
        <div className="messages-list">
          {messages.length === 0 && (
            <div className="welcome-message">
              <h2>Welcome! 👋</h2>
              <p>I can help you control a browser through natural language.</p>
              <div className="example-commands">
                <p><strong>Try these commands:</strong></p>
                <ul>
                  <li>"Find MacBook Air under ₹100000"</li>
                  <li>"Top 3 pizza places near Indiranagar with 4+ rating"</li>
                  <li>"Compare laptops on Flipkart and Amazon"</li>
                </ul>
              </div>
            </div>
          )}

          {messages.map(msg => (
            <MessageComponent key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your command..."
            disabled={!isConnected}
            className="message-input"
          />
          <button
            onClick={handleSend}
            disabled={!isConnected || !inputValue.trim()}
            className="send-button"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageComponent({ message }) {
  const { sender, text, variant, data, status } = message;

  return (
    <div className={`message ${sender}`}>
      <div className={`message-bubble ${variant} ${status || ''}`}>
        <div className="message-text">{text}</div>

        {data && (
          <div className="message-data">
            {data.type === 'plan' && data.plan && (
              <div className="plan-view">
                <strong>Action Plan:</strong>
                <ol>
                  {data.plan.slice(0, 5).map((step, idx) => (
                    <li key={idx}>
                      {step.action} {step.url ? `→ ${step.url}` : ''}
                      {step.target ? ` (${step.target})` : ''}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {data.type === 'result' && data.data && (
              <div className="results-view">
                {data.data.slice(0, data.count || 5).map((item, idx) => {
                  // Skip items with missing name
                  if (!item.name || item.name === 'N/A') {
                    return null;
                  }
                  
                  return (
                    <div key={idx} className="result-item">
                      <div className="result-name">{item.name}</div>
                      {item.price && item.price !== 'N/A' && item.price && parseInt(item.price) > 0 && (
                        <div className="result-price">₹{parseInt(item.price).toLocaleString('en-IN')}</div>
                      )}
                      {item.rating && item.rating !== 'N/A' && item.rating && (
                        <div className="result-rating">⭐ {item.rating}</div>
                      )}
                      {item.url && item.url !== 'N/A' && item.url && (
                        <a href={item.url} target="_blank" rel="noopener noreferrer" className="result-link">
                          View Details →
                        </a>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {data.action && (
              <div className="action-card">
                <span className="action-icon">{getActionIcon(data.action)}</span>
                <span className="action-name">{data.action}</span>
                {data.target && <span className="action-target">{data.target}</span>}
              </div>
            )}
          </div>
        )}
        
        <div className="message-time">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

function getActionIcon(action) {
  const icons = {
    navigate: '🌐',
    type: '⌨️',
    click: '👆',
    extract_products: '📦',
    filter_price: '💰',
    filter_rating: '⭐',
    wait_for: '⏳',
    fill_form_field: '📝',
    submit_form: '✅'
  };
  return icons[action] || '⚡';
}

export default App;

