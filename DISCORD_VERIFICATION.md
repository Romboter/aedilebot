# Discord Verified Apps Verification Journey

**Status:** Eligible for Verification  
**Application ID:** 1080333233075519581  
**Last Updated:** April 15, 2026

## Overview

Discord has notified aedilebot that it is eligible for the **Verified Apps** program. This document outlines the verification requirements, current implementation, options available, and the path forward.

## What is the Verified Apps Program?

The Verified Apps program is Discord's way of recognizing and promoting quality bots. Benefits include:

- **App Directory Listing** — Bots appear in Discord's app discovery store
- **Premium Apps** — Ability to monetize through premium features
- **Increased Reach** — Permission to join 100+ servers (required for scale)
- **Trust Badge** — Verified status visible to users

## Current State: Intents Used

### Privileged Intents (Require Approval)

| Intent | Status | Usage | Necessity |
|--------|--------|-------|-----------|
| **MESSAGE_CONTENT** | Enabled | Parses natural language text messages (e.g., "How many 40mm to kill X?") | Optional - Can be removed or limited |
| **GUILD_PRESENCES** | Enabled (default) | User presence tracking | Likely not needed |

### Non-Privileged Intents (No Approval Needed)

- GUILDS
- GUILD_MESSAGES (slash commands and message components)
- DIRECT_MESSAGES
- And others in `discord.Intents.default()`

## Current Functionality

### Slash Commands ✅ (No Privileged Intent Needed)
- `/kill [target] [weapon]` — Damage calculation
- `/disable [target] [weapon]` — Disable calculations
- `/dehusk [target] [weapon]` — Dehusk calculations
- `/bunker_kill [parameters]` — Complex bunker calculations
- `/statsheet [entity]` — Entity statistics
- `/custom_kill` — Custom damage queries
- `/help` — Help and command list

All slash commands include **autocomplete** for user-friendly discovery.

### Text Message Parsing ⚠️ (Requires MESSAGE_CONTENT Intent)
- Natural language parsing: "How many X to kill Y?"
- Currently works in all guild channels and DMs
- Defined in: [bot.py:507-511](src/bot.py#L507-L511) and [bot.py:607-637](src/bot.py#L607-L637)

## Verification Options

### Option 1: Full Verification (Recommended for Scale)
**Keep MESSAGE_CONTENT intent, request approval during verification**

**Pros:**
- Full functionality preserved
- Natural language parsing works everywhere
- Best UX for existing users
- Enables true bot scaling

**Cons:**
- Must request and justify MESSAGE_CONTENT intent during verification
- Verification process is more involved
- Discord will review use case for message parsing

**Implementation:**
- No code changes required
- Submit verification with both MESSAGE_CONTENT and GUILD_PRESENCES intents
- Explain use case: Damage calculator parses weapon/target names from user messages

---

### Option 2: Slash Commands Only (Simplest Verification)
**Remove MESSAGE_CONTENT intent entirely, rely on slash commands**

**Pros:**
- No privileged intents to approve
- Faster, simpler verification process
- Cleaner permission footprint
- Better mobile UX (autocomplete)
- Slash commands are Discord's recommended path

**Cons:**
- Removes natural language parsing capability
- Existing text-based users must migrate to slash commands
- Less powerful for casual/experimental use

**Implementation:**
```python
# In bot.py, remove these lines:
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    user_message = str(message.content)
    await main.message_handler(message, user_message)
```

Also remove `intents.message_content = True` from bot initialization.

---

### Option 3: Hybrid Approach (Recommended Balance)
**Keep MESSAGE_CONTENT intent but limit to DMs and @mentions only**

**Pros:**
- Natural language parsing still available for power users
- DM access doesn't need privileged intent (Discord allows this)
- @mention access doesn't need privileged intent (Discord allows this)
- Simplifies verification (technically no privileged intent required)
- Maintains advanced UX for dedicated users

**Cons:**
- Requires code modification
- Users must know to @mention bot or use DMs
- Less discoverable than guild-wide parsing

**Implementation:**
Modify the `on_message` handler in [bot.py:507-511](src/bot.py#L507-L511):

```python
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    # Only process in DMs or when bot is mentioned
    if message.guild is not None and client.user not in message.mentions:
        return
    
    user_message = str(message.content)
    await main.message_handler(message, user_message)
```

Remove `intents.message_content = True` from bot initialization since Discord provides message content in these contexts without the intent.

---

## GUILD_PRESENCES Intent

**Current Status:** Enabled (included in `discord.Intents.default()`)  
**Usage in Code:** Not obviously used  
**Recommendation:** Disable during verification unless needed

To remove:
```python
intents = discord.Intents.default()
intents.presences = False  # Explicitly disable
```

## Verification Checklist

- [ ] Decide on verification approach (Option 1, 2, or 3)
- [ ] Implement code changes if needed
- [ ] Finalize bot description and purpose
- [ ] Prepare screenshots/demo of bot functionality
- [ ] Explain MESSAGE_CONTENT usage (if keeping it)
- [ ] Prepare privacy policy (if not already existing)
- [ ] Initiate verification: https://discord.com/developers/applications/1080333233075519581/verification-onboarding
- [ ] Respond to Discord's questions about bot use case
- [ ] Wait for approval (typically 3-7 days)

## Timeline

- **April 15, 2026** — Discord notification of Verified Apps eligibility received
- **TBD** — Decision on verification approach
- **TBD** — Code modifications (if needed)
- **TBD** — Verification submission
- **TBD** — Approval expected

## References

- [Discord Verified Apps Program](https://support-dev.discord.com/hc/articles/23926564536471)
- [App Directory](https://support-apps.discord.com/hc/articles/26592957841303-How-to-Discover-and-Add-Apps)
- [Privileged Intents](https://support-dev.discord.com/hc/articles/6207308062871)
- [Message Content Intent Alternatives](https://support-dev.discord.com/hc/en-us/articles/6383579033751-Message-Content-Intent-Alternatives)

## Next Steps

1. Review the three options above
2. Decide which path aligns with aedilebot's goals
3. Implement any necessary code changes
4. Submit verification when ready
5. Update this document with progress and outcomes
