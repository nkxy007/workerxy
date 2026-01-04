# Phase 1: Session Continuity - Testing Guide

## ✅ What Was Implemented

### 1. Full Conversation History
- Agent now receives **all previous messages** in the conversation
- Each message includes role (user/assistant) and content
- Agent can reference and build upon previous exchanges

### 2. Enhanced Logging
- Shows conversation history length: `📜 Conversation history length: X messages`
- Logs message roles: `History preview: ['user', 'assistant', 'user']`
- Confirms context sent to agent: `📨 Sending X messages to agent (with full context)`

### 3. Session Info Display
- Sidebar now shows:
  - 💬 **Current Task** section
  - 🔗 Conversation context indicator
  - 🆔 Session ID (last 8 chars)
  - Message count

---

## 🧪 Testing Scenarios

### Test 1: Basic Context Continuity ⭐ **Most Important**

**Goal:** Verify agent remembers previous questions

**Steps:**
1. Start fresh (click "New Task" if needed)
2. **Message 1:** `"What is the broadcast address of 192.168.16.0/28?"`
3. Wait for response
4. **Message 2:** `"What about for /27?"` ← No subnet specified!

**Expected Result:**
- Agent should understand "/27" refers to 192.168.16.0
- Response should be: "For 192.168.16.0/27, the broadcast address is 192.168.16.31"

**Logs to Check:**
```
📜 Conversation history length: 1 messages  (first message)
📜 Conversation history length: 3 messages  (second message: user, assistant, user)
📨 Sending 3 messages to agent (with full context)
```

---

### Test 2: Multi-Turn Troubleshooting

**Goal:** Verify agent maintains context across multiple exchanges

**Conversation:**
```
User: "User with IP 10.10.10.4 can't reach the internet"
Agent: [responds with questions]

User: "They're connected to switch 192.168.1.1 port 24"
Agent: [should remember the user IP 10.10.10.4]

User: "What should I check next?"
Agent: [should remember both the IP and switch info]
```

**Expected Result:**
- Agent references IP 10.10.10.4 without you repeating it
- Agent knows which switch you're talking about
- Agent builds troubleshooting steps based on previous answers

**Logs to Check:**
```
📜 Conversation history length: 5 messages
(or more, depending on exchanges)
```

---

### Test 3: Pronoun Resolution

**Goal:** Agent resolves pronouns using context

**Conversation:**
```
User: "Show me the routing table for 192.168.50.1"
Agent: [shows routing table]

User: "What about its neighbor?"  ← "its" should refer to 192.168.50.1
```

**Expected Result:**
- Agent knows "its" = 192.168.50.1
- Agent asks for or finds neighbor information

---

### Test 4: Session Isolation (Critical!)

**Goal:** Verify "New Task" actually clears context

**Steps:**
1. Have a conversation about Topic A (e.g., IP 10.10.10.4)
2. **Click "New Task"** button in sidebar
3. Check logs: Should see `clear_session` called
4. Start new conversation about Topic B (e.g., IP 192.168.1.1)
5. Ask: "What IP were we troubleshooting?" ← Should NOT know about 10.10.10.4

**Expected Result:**
- Agent should NOT remember Topic A after "New Task"
- Session stats should reset to 0 messages
- New session ID displayed in sidebar

**Logs to Check:**
```
(After New Task click)
📜 Conversation history length: 1 messages  (fresh start)
```

---

### Test 5: Long Conversation

**Goal:** Verify context accumulates correctly

**Steps:**
1. Have 10+ back-and-forth exchanges
2. Watch sidebar message count increase
3. Check logs for increasing history length

**Expected Result:**
- Message count increases: 2, 4, 6, 8, 10, 12...
- Logs show: `📜 Conversation history length: 21 messages` (after 10 exchanges)
- Agent can still reference early messages

**Example:**
```
Exchange 1: Discuss switch A
Exchange 2: Discuss VLAN config
...
Exchange 10: Ask "What was that switch we started with?"
Agent: Should remember switch A from Exchange 1!
```

---

## 📊 What to Monitor

### In Console Logs:
✅ **Every message should show:**
```
📜 Conversation history length: X messages
📨 Sending X messages to agent (with full context)
History preview: ['user', 'assistant', 'user', ...]
```

✅ **History should grow:**
```
Message 1: 1 messages
Message 2: 3 messages (user, assistant, user)
Message 3: 5 messages
Message 4: 7 messages
```

### In UI Sidebar:
✅ **Session Stats section shows:**
- Messages count increasing
- Artifacts count (if any generated)

✅ **Current Task section shows:**
- "🔗 Conversation has context (X messages)"
- Session ID (last 8 chars)

### In Chat:
✅ **Agent behavior:**
- References previous messages naturally
- Doesn't ask for information already provided
- Builds on previous answers
- Uses pronouns correctly (it, that, etc.)

---

## 🐛 Troubleshooting

### Issue: Agent doesn't remember previous messages

**Check logs for:**
```
📜 Conversation history length: 1 messages
(should be more on 2nd+ message)
```

**If always 1 message:**
- SessionManager not storing messages properly
- Check if `add_message()` is being called

**If shows correct count but agent still forgets:**
- Agent may not be using the history properly
- Check agent_input format in logs

---

### Issue: Context from previous task leaks into new task

**After clicking "New Task":**
```
📜 Conversation history length: X messages
(should be 1 on first message of new task)
```

**If not 1:**
- `clear_session()` not working
- Session ID not changing

---

### Issue: Message count doesn't match conversation

**Check:**
- UI shows: Messages = X
- Logs show: `Conversation history length: Y messages`
- X should equal Y

**If mismatch:**
- UI and backend out of sync
- Refresh page and check again

---

## ✨ Success Indicators

### ✅ You'll Know It's Working When:

1. **Agent uses context naturally:**
   ```
   You: "Check IP 10.10.10.4"
   Agent: [checks]
   You: "Ping it from the gateway"
   Agent: "Pinging 10.10.10.4 from gateway..." ← Remembered the IP!
   ```

2. **Logs show growing history:**
   ```
   1 messages → 3 messages → 5 messages → 7 messages
   ```

3. **Sidebar updates correctly:**
   ```
   Messages: 0 → 2 → 4 → 6 → 8
   ```

4. **New Task actually resets:**
   ```
   Before New Task: 10 messages
   After New Task: 0 messages
   First message after: 1 message
   ```

---

## 📝 Example Test Session

### Complete Test Flow:

```bash
# Terminal
cd /home/toffe/workspace/agentic
conda activate test_langchain_env
streamlit run ui/app.py
```

**In Browser:**

1. **First Message:**
   - Type: `"What is the broadcast address of 192.168.16.0/28?"`
   - Check sidebar: Messages = 2 (your question + agent response)
   - Check logs: `📜 Conversation history length: 1 messages`

2. **Second Message:**
   - Type: `"What about /27?"`
   - Check sidebar: Messages = 4
   - Check logs: `📜 Conversation history length: 3 messages`
   - **Agent should know you mean 192.168.16.0**

3. **Third Message:**
   - Type: `"And for that subnet, what's the network address?"`
   - Check sidebar: Messages = 6
   - Check logs: `📜 Conversation history length: 5 messages`
   - **Agent should know "that subnet" = 192.168.16.0/27**

4. **Reset:**
   - Click "🆕 New Task"
   - Check sidebar: Messages = 0
   - Check: "🆕 New task - no messages yet"

5. **After Reset:**
   - Type: `"What were we discussing?"`
   - **Agent should NOT remember anything about 192.168.16.0**

---

## 🎯 Key Differences: Before vs After

### Before Phase 1:
```
You: "What is 192.168.16.0/28 broadcast?"
Agent: "It's 192.168.16.15"

You: "What about /27?"
Agent: "Which subnet are you asking about?" ← NO CONTEXT
```

### After Phase 1:
```
You: "What is 192.168.16.0/28 broadcast?"
Agent: "It's 192.168.16.15"

You: "What about /27?"
Agent: "For 192.168.16.0/27, it's 192.168.16.31" ← HAS CONTEXT!
```

---

## 📈 Expected Log Pattern

```
=== First Message ===
INFO - Send button clicked. User input: What is the broadcast...
INFO - Stream response started for session abc123...
INFO - 📜 Conversation history length: 1 messages
DEBUG - History preview: ['user']
INFO - 📨 Sending 1 messages to agent (with full context)

=== Second Message ===
INFO - Send button clicked. User input: What about /27?...
INFO - Stream response started for session abc123...
INFO - 📜 Conversation history length: 3 messages
DEBUG - History preview: ['user', 'assistant', 'user']
INFO - 📨 Sending 3 messages to agent (with full context)

=== After clicking New Task ===
(Session cleared)

=== First Message in New Task ===
INFO - 📜 Conversation history length: 1 messages
(Back to 1 message)
```

---

## 🚀 Ready to Test!

Run the app and try the test scenarios above. The most important test is **Test 1** - if the agent can answer "What about /27?" without you specifying the subnet, **Phase 1 is working!**

Good luck! 🎉
