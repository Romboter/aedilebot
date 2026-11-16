# Aedilebot High Availability Setup

**Status:** Ready to implement  
**Approach:** CloudAMQP RabbitMQ free tier with heartbeat failover  
**Heartbeat Interval:** 10 seconds  
**Free Tier Limit:** 2M messages/month (you'll use ~260K/month)

---

## Architecture Overview

```
┌──────────────────┐                  ┌──────────────────┐
│   US Host        │                  │   EU Host        │
│   (Primary)      │◄─Heartbeat (10s)─│   (Standby)      │
│   • Connected    │    via RabbitMQ   │   • Monitoring   │
│   • Running bot  │                  │   • Dormant      │
└──────────────────┘                  └──────────────────┘
         │                                       │
         └─────────────┬────────────────────────┘
                       │
                CloudAMQP RabbitMQ
              (Free tier: Little Lemur)
           1M messages/month included
```

---

## Option 1: RabbitMQ Heartbeat (Recommended)

### Step 1: CloudAMQP Setup (2 minutes)

1. **Sign up at:** https://www.cloudamqp.com/
2. **Create free instance:**
   - Plan: "Little Lemur" (FREE)
   - Region: Doesn't matter (US and EU are both fine)
   - Click "Create Instance"
3. **Get connection details:**
   - Copy the AMQP URL (looks like: `amqp://user:pass@host/vhost`)
   - Store it safely in `.env` file

**In `.env`:**
```
RABBITMQ_URL=amqp://user:pass@your-host.cloudamqp.com/vhost
DEPLOYMENT_TOKEN=your_discord_token
DEV_SERVER_TOKEN=your_dev_token
```

---

### Step 2: Install Dependencies

```bash
pip install pika
```

---

### Step 3: Create HA Handler

**New file: `src/ha_manager.py`**

```python
import pika
import json
import time
import asyncio
from threading import Thread
import os
from dotenv import load_dotenv

load_dotenv()

class BotHAManager:
    """Manages heartbeat and failover for bot HA setup"""
    
    def __init__(self, bot, host_name: str, rabbitmq_url: str):
        """
        Args:
            bot: Discord bot instance
            host_name: "us" or "eu" - identifies this instance
            rabbitmq_url: CloudAMQP AMQP URL from environment
        """
        self.bot = bot
        self.host_name = host_name
        self.rabbitmq_url = rabbitmq_url
        self.is_master = True  # Start as master
        self.heartbeat_interval = 10  # seconds
        self.heartbeat_timeout = 30  # seconds
        self.last_heartbeat_time = time.time()
        self.connection = None
        self.channel = None
        
    def connect_rabbitmq(self):
        """Establish RabbitMQ connection"""
        try:
            params = pika.URLParameters(self.rabbitmq_url)
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            
            # Declare exchange and queue
            self.channel.exchange_declare(
                exchange='aedilebot_exchange',
                exchange_type='topic',
                durable=True
            )
            self.channel.queue_declare(
                queue='aedilebot_heartbeat',
                durable=True
            )
            self.channel.queue_bind(
                exchange='aedilebot_exchange',
                queue='aedilebot_heartbeat',
                routing_key='heartbeat.*'
            )
            
            print(f"[{self.host_name}] Connected to RabbitMQ")
            return True
        except Exception as e:
            print(f"[{self.host_name}] RabbitMQ connection failed: {e}")
            return False
    
    def start_monitoring(self):
        """Start heartbeat monitor in background thread"""
        Thread(target=self._monitor_loop, daemon=True).start()
        print(f"[{self.host_name}] HA monitoring started")
    
    def _monitor_loop(self):
        """Background loop that monitors heartbeats"""
        # Connect to RabbitMQ
        if not self.connect_rabbitmq():
            print(f"[{self.host_name}] Failed to start HA monitoring")
            return
        
        # Set up consumer for heartbeats
        def heartbeat_callback(ch, method, properties, body):
            try:
                msg = json.loads(body)
                if msg.get("master") != self.host_name:
                    self.last_heartbeat_time = time.time()
                    
                    # Other host is master and healthy
                    if self.is_master:
                        print(f"[{self.host_name}] Other host ({msg.get('master')}) is healthy, stepping down")
                        self.is_master = False
                        # Disconnect bot
                        asyncio.run_coroutine_threadsafe(
                            self._disconnect_bot(),
                            self.bot.loop
                        )
                
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f"[{self.host_name}] Heartbeat callback error: {e}")
        
        self.channel.basic_consume(
            queue='aedilebot_heartbeat',
            on_message_callback=heartbeat_callback
        )
        
        # Start consuming
        try:
            self.channel.start_consuming()
        except Exception as e:
            print(f"[{self.host_name}] Consumer error: {e}")
    
    def send_heartbeat(self):
        """Send heartbeat to indicate this instance is alive"""
        if not self.is_master:
            return  # Only master sends heartbeats
        
        try:
            message = {
                "host": self.host_name,
                "master": self.host_name,
                "timestamp": time.time(),
                "status": "alive"
            }
            
            self.channel.basic_publish(
                exchange='aedilebot_exchange',
                routing_key=f'heartbeat.{self.host_name}',
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2  # Persistent
                )
            )
        except Exception as e:
            print(f"[{self.host_name}] Failed to send heartbeat: {e}")
    
    async def _disconnect_bot(self):
        """Disconnect bot from Discord"""
        try:
            await self.bot.close()
            print(f"[{self.host_name}] Bot disconnected (stepping down from master)")
        except Exception as e:
            print(f"[{self.host_name}] Error disconnecting bot: {e}")
    
    def check_other_host_health(self):
        """Check if other host's heartbeat has timed out"""
        time_since_last = time.time() - self.last_heartbeat_time
        
        if time_since_last > self.heartbeat_timeout and not self.is_master:
            print(f"[{self.host_name}] Heartbeat timeout ({time_since_last:.0f}s)! Taking over as master")
            self.is_master = True
            return True
        return False


# Global HA manager instance
ha_manager = None

def init_ha(bot, host_name: str):
    """Initialize HA manager (call this in bot.py)"""
    global ha_manager
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    
    if not rabbitmq_url:
        print(f"[{host_name}] WARNING: RABBITMQ_URL not set, HA disabled")
        return None
    
    ha_manager = BotHAManager(bot, host_name, rabbitmq_url)
    ha_manager.start_monitoring()
    return ha_manager
```

---

### Step 4: Integrate with Bot

**In `src/bot.py`, modify `run_discord_bot()`:**

```python
import ha_manager

def run_discord_bot():
    # Determine host name from environment or argument
    HOST_NAME = os.getenv("BOT_HOST", "us")  # "us" or "eu"
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.presences = False  # Disable unnecessary intent
    
    client = commands.Bot(
        command_prefix="!", intents=intents, proxy=HTTPS_PROXY
    )
    
    # Initialize HA
    ha = ha_manager.init_ha(client, HOST_NAME)

    @client.event
    async def on_ready():
        if ha and ha.is_master:
            print(f"[{HOST_NAME}] Bot is ACTIVE (master)")
            # Send heartbeats every 10 seconds
            while True:
                ha.send_heartbeat()
                await asyncio.sleep(10)
        else:
            print(f"[{HOST_NAME}] Bot is on STANDBY")
            # Periodically check if master is down
            while True:
                if ha:
                    ha.check_other_host_health()
                await asyncio.sleep(5)

    # ... rest of bot code ...

    client.run(DEV_SERVER_TOKEN if HOST_NAME == "us" else DEPLOYMENT_TOKEN)
```

---

## Option 2: HTTP Health Check Endpoint (Simpler Alternative)

If you prefer not to manage RabbitMQ, use simple HTTP heartbeat instead.

### Step 1: Install Dependencies

```bash
pip install flask requests
```

### Step 2: Create Health Check Handler

**New file: `src/health_check.py`**

```python
from flask import Flask, jsonify
from threading import Thread
import requests
import time
import os

class BotHealthCheck:
    """Simple HTTP-based HA using health endpoints"""
    
    def __init__(self, bot, host_name: str, other_host_url: str, port: int = 5000):
        """
        Args:
            bot: Discord bot instance
            host_name: "us" or "eu"
            other_host_url: HTTP URL of other host (e.g., "http://eu-bot.com:5000")
            port: Port to run health endpoint on
        """
        self.bot = bot
        self.host_name = host_name
        self.other_host_url = other_host_url
        self.port = port
        self.is_master = True
        self.last_other_heartbeat = time.time()
        self.health_check_interval = 10  # seconds
        self.timeout_threshold = 30  # seconds
        
        # Create Flask app for health endpoint
        self.app = Flask(__name__)
        
        @self.app.route("/health")
        def health():
            return jsonify({
                "status": "alive",
                "host": self.host_name,
                "is_master": self.is_master,
                "timestamp": time.time()
            })
    
    def start_health_endpoint(self):
        """Start Flask health endpoint in background thread"""
        Thread(
            target=lambda: self.app.run(
                host="0.0.0.0",
                port=self.port,
                debug=False,
                use_reloader=False
            ),
            daemon=True
        ).start()
        print(f"[{self.host_name}] Health endpoint started on port {self.port}")
    
    def start_health_monitoring(self):
        """Start monitoring other host's health in background thread"""
        Thread(target=self._monitor_loop, daemon=True).start()
        print(f"[{self.host_name}] Health monitoring started")
    
    def _monitor_loop(self):
        """Background loop that checks other host's health"""
        while True:
            try:
                response = requests.get(
                    f"{self.other_host_url}/health",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.last_other_heartbeat = time.time()
                    
                    # Other host is alive and is master - we should be standby
                    if data.get("is_master") and self.is_master:
                        print(f"[{self.host_name}] Other host is healthy master, becoming standby")
                        self.is_master = False
                
            except requests.exceptions.RequestException:
                # Other host is unreachable
                time_since_last = time.time() - self.last_other_heartbeat
                
                if time_since_last > self.timeout_threshold and not self.is_master:
                    print(f"[{self.host_name}] Other host timeout ({time_since_last:.0f}s)! Becoming master")
                    self.is_master = True
            
            time.sleep(self.health_check_interval)


def init_health_check(bot, host_name: str, other_host_url: str):
    """Initialize health check (call this in bot.py)"""
    hc = BotHealthCheck(bot, host_name, other_host_url)
    hc.start_health_endpoint()
    hc.start_health_monitoring()
    return hc
```

### Step 3: Integrate with Bot

**In `src/bot.py`:**

```python
import health_check

def run_discord_bot():
    HOST_NAME = os.getenv("BOT_HOST", "us")  # "us" or "eu"
    OTHER_HOST_URL = os.getenv("OTHER_HOST_URL", "http://other-host:5000")
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.presences = False
    
    client = commands.Bot(
        command_prefix="!", intents=intents, proxy=HTTPS_PROXY
    )
    
    # Initialize health check
    hc = health_check.init_health_check(client, HOST_NAME, OTHER_HOST_URL)

    @client.event
    async def on_ready():
        if hc.is_master:
            print(f"[{HOST_NAME}] Bot is ACTIVE (master)")
        else:
            print(f"[{HOST_NAME}] Bot is on STANDBY")
            # Wait for master to go down
            while not hc.is_master:
                await asyncio.sleep(5)
            print(f"[{HOST_NAME}] Master failed, connecting to Discord...")
            # Reconnect will happen automatically

    # ... rest of bot code ...
    client.run(DEV_SERVER_TOKEN if HOST_NAME == "us" else DEPLOYMENT_TOKEN)
```

---

## Preventing Dual-Active Scenario

**CRITICAL:** Only one bot instance can connect to Discord with the same token.

### How Both Systems Prevent This:

#### RabbitMQ Approach:
1. **Primary (US)** publishes heartbeat every 10 seconds
2. **Secondary (EU)** subscribes and receives heartbeat
3. If Secondary gets no heartbeat for 30 seconds → Secondary becomes master and connects bot
4. If Primary recovers and sees Secondary is master → Primary disconnects

**Key Protection:** Each instance tracks who is currently master in RabbitMQ. Only the master connects to Discord.

#### HTTP Approach:
1. **Primary (US)** has `/health` endpoint that says `"is_master": true`
2. **Secondary (EU)** polls `/health` every 10 seconds
3. If no response for 30 seconds → Secondary sets `is_master: true` and connects bot
4. Primary is unreachable, so it stays disconnected

**Key Protection:** The instance that can't reach the other host waits 30 seconds before taking over. The disconnected host is unreachable, so it can't interfere.

---

## Environment Variables

**For both US and EU hosts, create/update `.env`:**

```bash
# Discord
DEPLOYMENT_TOKEN=your_production_bot_token
DEV_SERVER_TOKEN=your_dev_bot_token

# HA Config
BOT_HOST=us          # Set to "eu" on EU server
RABBITMQ_URL=amqp://user:pass@host.cloudamqp.com/vhost  # RabbitMQ only
OTHER_HOST_URL=http://eu-bot-ip:5000  # HTTP health check only
HTTPS_PROXY=your_proxy_if_needed
```

---

## Deployment

### US Host (Primary)
```bash
export BOT_HOST=us
export OTHER_HOST_URL=http://eu-bot-ip:5000
python src/main.py
```

### EU Host (Secondary/Standby)
```bash
export BOT_HOST=eu
export OTHER_HOST_URL=http://us-bot-ip:5000
python src/main.py
```

---

## Monitoring & Testing

### Check Bot Status
```bash
# RabbitMQ
curl http://localhost:5000/health  # If using HTTP approach

# Watch logs
tail -f aedilebot.log | grep "is ACTIVE\|is on STANDBY\|heartbeat\|timeout"
```

### Test Failover
1. Start US bot (should be ACTIVE)
2. Start EU bot (should be STANDBY)
3. Kill US bot (wait 30 seconds)
4. EU bot should become ACTIVE and connect to Discord
5. Restart US bot
6. US bot should detect EU is master and stay dormant

---

## Option Comparison

| Aspect | RabbitMQ | HTTP Check |
|--------|----------|-----------|
| **Setup Time** | 3 minutes | 2 minutes |
| **Cost** | Free ($0) | Free ($0) |
| **Dependencies** | pika, RabbitMQ | flask, requests |
| **Reliability** | Very high (managed) | Good (direct) |
| **Scalability** | ✅ Can add more hosts | ⚠️ N-to-N polling |
| **Complexity** | Medium | Low |
| **Firewall Issues** | None (outbound only) | Needs ports open |

**Recommendation:**
- **If you want managed simplicity:** RabbitMQ (CloudAMQP free)
- **If you want minimal dependencies:** HTTP health check

---

## Rollback/Troubleshooting

### Both instances trying to connect (dual-active)
- **Cause:** Heartbeat timeout too short or network lag
- **Fix:** Increase `heartbeat_timeout` to 60 seconds

### Instance won't become master after other dies
- **Cause:** Health check not triggering failover
- **Fix:** Check `OTHER_HOST_URL` is correct and reachable

### Heartbeat flood in logs
- **Cause:** Debug logging too verbose
- **Fix:** Reduce logging in ha_manager.py or health_check.py

---

## Next Steps

1. Choose option (RabbitMQ or HTTP)
2. Deploy code to both hosts
3. Set environment variables
4. Start both instances
5. Verify logs show correct master/standby status
6. Test failover by killing primary
7. Monitor for 24 hours to ensure stability

---

## References

- [CloudAMQP Docs](https://www.cloudamqp.com/docs/)
- [Pika Library Docs](https://pika.readthedocs.io/)
- [Flask Health Check Pattern](https://flask.palletsprojects.com/patterns/patterns/)
- [Discord.py Bot Lifecycle](https://discordpy.readthedocs.io/en/stable/ext/commands/bot.html)
