# Running as a Linux Daemon (FREE/Cheap Solution!)

**Perfect for running on a budget!** No expensive cloud hosting needed.

---

## 💰 **Cost Options**

| Option | Cost | Pros | Cons |
|--------|------|------|------|
| **Your Linux PC** | **FREE** | No cost, full control | Must keep PC on |
| **Raspberry Pi** | **$35-75 one-time** | Low power, always on | Initial hardware cost |
| **VPS (DigitalOcean)** | **$5-6/month** | Professional, reliable | Ongoing cost |
| **Old Laptop** | **FREE** | Repurpose old hardware | Power consumption |

**Recommended:** Start with your Linux PC (free!), then upgrade to VPS if profitable.

---

## 🚀 **Quick Setup (5 minutes)**

### **Step 1: Install the Daemon**

```bash
# Make scripts executable
chmod +x scripts/install-daemon.sh
chmod +x scripts/manage-daemon.sh

# Run installation
./scripts/install-daemon.sh
```

### **Step 2: Enable Auto-Start**

```bash
# Enable service
./scripts/manage-daemon.sh enable

# This enables:
# ✅ Auto-start on boot
# ✅ Run when you're not logged in
# ✅ Auto-restart if crashes
```

### **Step 3: Start the Service**

```bash
# Start monitoring now
./scripts/manage-daemon.sh start

# Check it's running
./scripts/manage-daemon.sh status
```

**That's it! The system is now running 24/7 in the background!** 🎉

---

## 📊 **Managing the Daemon**

### **Common Commands**

```bash
# Start/Stop/Restart
./scripts/manage-daemon.sh start
./scripts/manage-daemon.sh stop
./scripts/manage-daemon.sh restart

# Check status
./scripts/manage-daemon.sh status

# View live logs
./scripts/manage-daemon.sh logs

# View log file
./scripts/manage-daemon.sh logs-file
```

### **Check What It's Doing**

```bash
# Watch live activity
tail -f logs/daemon.log

# Check for errors
tail -f logs/daemon-error.log

# See systemd journal
journalctl --user -u betting-advisor -f
```

---

## 🔧 **Configuration**

### **Change Check Interval**

Edit the service file to change how often it checks for opportunities:

```bash
# Edit service
nano ~/.config/systemd/user/betting-advisor.service

# Change this line (3600 = 1 hour):
ExecStart=.../scripts/multi_league_tracker.py --interval 3600

# Change to 30 minutes (1800 seconds):
ExecStart=.../scripts/multi_league_tracker.py --interval 1800

# Reload and restart
systemctl --user daemon-reload
./scripts/manage-daemon.sh restart
```

### **Select Specific Leagues**

To save API calls, only monitor specific leagues:

```bash
# Edit service file
nano ~/.config/systemd/user/betting-advisor.service

# Change ExecStart line to:
ExecStart=.../multi_league_tracker.py --interval 3600 --leagues soccer_epl soccer_spain_la_liga

# Reload and restart
systemctl --user daemon-reload
./scripts/manage-daemon.sh restart
```

### **Resource Limits**

Already configured for low resource usage:
- **Memory:** Max 512MB (adjust in service file)
- **CPU:** Max 50% of one core (adjust in service file)

---

## 📱 **Getting Notifications**

### **Option 1: Email Alerts (Free)**

Add to your cron to get daily summaries:

```bash
# Edit crontab
crontab -e

# Add this line (daily summary at 9 PM):
0 21 * * * /path/to/project/scripts/dashboard.py | mail -s "Betting Advisor Daily Report" your@email.com
```

### **Option 2: Telegram Bot (Free)**

1. Create Telegram bot via @BotFather
2. Get your chat ID
3. Add to `multi_league_tracker.py`:

```python
# In save_opportunities method, add:
if opportunities:
    import requests
    BOT_TOKEN = "your_bot_token"
    CHAT_ID = "your_chat_id"
    message = f"🎯 Found {len(opportunities)} betting opportunities!"
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": message}
    )
```

### **Option 3: Pushover ($5 one-time)**

1. Sign up at pushover.net
2. Install app on phone
3. Add to script:

```python
import requests
requests.post("https://api.pushover.net/1/messages.json", data={
    "token": "YOUR_APP_TOKEN",
    "user": "YOUR_USER_KEY",
    "message": "Opportunities found!"
})
```

---

## 🏠 **Running on Different Systems**

### **Your Linux Desktop/Laptop (FREE)**

**Pros:**
- ✅ No cost
- ✅ Full control
- ✅ Easy to monitor

**Cons:**
- ❌ Must keep PC on
- ❌ Power consumption

**Setup:** Use the installation above. Done!

---

### **Raspberry Pi (Best Budget Option)**

**Cost:** $35-75 one-time  
**Power:** ~$2-3/year electricity

**Pros:**
- ✅ Low power (3-5W)
- ✅ Silent, always on
- ✅ Perfect for this task

**Setup:**
1. Install Raspberry Pi OS
2. Clone project to Pi
3. Run same installation
4. Place Pi near router, plug in, forget about it!

**Recommendation:** Raspberry Pi 4 (2GB) is perfect for this.

---

### **VPS (DigitalOcean/Linode)**

**Cost:** $5-6/month

**Pros:**
- ✅ Always on
- ✅ Professional reliability
- ✅ No hardware to maintain
- ✅ Fast internet

**Cons:**
- ❌ Ongoing cost

**Setup on DigitalOcean:**
```bash
# 1. Create $5/month droplet (Ubuntu 22.04)
# 2. SSH into server
ssh root@your_server_ip

# 3. Clone and setup
git clone https://github.com/yourusername/betting-expert-advisor.git
cd betting-expert-advisor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Add API key to .env
nano .env

# 5. Install daemon
./scripts/install-daemon.sh
./scripts/manage-daemon.sh enable
./scripts/manage-daemon.sh start

# 6. Done! Logout and it keeps running
```

---

## 🔍 **Monitoring & Maintenance**

### **Daily Checks**

```bash
# Quick status check
./scripts/manage-daemon.sh status

# View today's opportunities
tail -50 logs/daemon.log | grep "🎯"

# Check API usage
grep "requests remaining" logs/daemon.log | tail -1
```

### **Weekly Maintenance**

```bash
# Rotate logs (prevent large files)
./scripts/manage-daemon.sh stop
mv logs/daemon.log logs/daemon.log.old
./scripts/manage-daemon.sh start

# Or setup logrotate (automatic):
sudo nano /etc/logrotate.d/betting-advisor
```

Add this to logrotate:
```
/home/evans/Projects/Betting Expert Advisor/logs/*.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
}
```

### **Monthly**

```bash
# Update the system
git pull origin main
./scripts/manage-daemon.sh restart

# Check performance
./scripts/paper_trading_report.py
```

---

## 🚨 **Troubleshooting**

### **Service Won't Start**

```bash
# Check errors
./scripts/manage-daemon.sh status

# View detailed logs
journalctl --user -u betting-advisor -n 50

# Check error log
cat logs/daemon-error.log
```

### **Not Running After Reboot**

```bash
# Enable lingering (required for user services)
sudo loginctl enable-linger $USER

# Re-enable service
./scripts/manage-daemon.sh enable
```

### **High Memory/CPU Usage**

```bash
# Check resource usage
systemctl --user status betting-advisor

# Adjust limits in service file
nano ~/.config/systemd/user/betting-advisor.service

# Change:
MemoryMax=512M  # Lower if needed
CPUQuota=25%    # Lower if needed

# Reload
systemctl --user daemon-reload
./scripts/manage-daemon.sh restart
```

---

## 📊 **What the Daemon Does**

### **Every Hour (Configurable):**
1. ✅ Fetches live odds from TheOddsAPI
2. ✅ Checks all configured leagues (default: 7 leagues)
3. ✅ Runs ML model predictions
4. ✅ Identifies value bets (>1% edge)
5. ✅ Saves opportunities to JSON
6. ✅ Logs all activity

### **Resource Usage:**
- **Memory:** ~100-300MB
- **CPU:** <5% average
- **Disk:** ~10MB logs per week
- **Network:** ~5-10 API calls per hour

### **API Efficiency:**
With caching enabled:
- First check: 7-14 API calls
- Subsequent checks: 0-7 calls (90% cached)
- Monthly: ~200-300 calls (under 500 limit)

---

## 💡 **Money-Saving Tips**

### **1. Run on Your PC (Free)**
- Keep your Linux machine on 24/7
- Uses negligible resources
- Monitor anytime

### **2. Use a Raspberry Pi ($35)**
- One-time cost
- $2-3/year electricity
- Silent, always on
- Perfect for this task

### **3. Optimize API Usage**
```bash
# Check fewer leagues (use 2-3 instead of 7)
--leagues soccer_epl soccer_spain_la_liga

# Check less frequently (every 2 hours instead of 1)
--interval 7200
```

### **4. Start Small**
1. **Week 1-2:** Paper trade on your PC
2. **Week 3-4:** If profitable, continue or upgrade to Pi
3. **Month 2+:** If consistently profitable, consider VPS

---

## 🎯 **Recommended Setup for Broke Students/Beginners**

```bash
# 1. Use your existing Linux PC (FREE)
./scripts/install-daemon.sh
./scripts/manage-daemon.sh enable
./scripts/manage-daemon.sh start

# 2. Configure for low API usage (3 leagues, every 2 hours)
# Edit service file
nano ~/.config/systemd/user/betting-advisor.service

# Change to:
ExecStart=.../multi_league_tracker.py --interval 7200 --leagues soccer_epl soccer_spain_la_liga soccer_uefa_champs_league

# 3. Set up free Telegram notifications
# (See Telegram Bot section above)

# 4. Check daily
./scripts/dashboard.py

# 5. Paper trade for 4 weeks before real money

# Total cost: $0 🎉
```

---

## ✅ **Final Checklist**

- [ ] Daemon installed
- [ ] Auto-start enabled
- [ ] Service running
- [ ] Logs working
- [ ] API key configured
- [ ] Notifications setup (optional)
- [ ] Tested restart/reboot
- [ ] Monitoring working

---

## 📞 **Quick Reference**

```bash
# Installation
./scripts/install-daemon.sh

# Management
./scripts/manage-daemon.sh {start|stop|restart|status|logs|enable|disable}

# Check activity
tail -f logs/daemon.log

# Daily summary
./scripts/dashboard.py

# Paper trading report
./scripts/paper_trading_report.py
```

---

**You're now running a professional 24/7 betting system for FREE (or <$10/month)!** 🚀💰

No expensive cloud hosting needed. Perfect for broke students and beginners!

---

*Last updated: October 29, 2025*
