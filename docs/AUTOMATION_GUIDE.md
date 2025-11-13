# Automated Monitoring Setup Guide

Complete guide to set up automated daily monitoring of betting opportunities.

---

## 📅 **Daily Monitoring Script**

The system includes `scripts/daily_monitor.sh` which:
- Checks system status via dashboard
- Scans all configured leagues for opportunities
- Logs results to `logs/daily_checks/`
- Can be scheduled to run automatically

---

## ⚙️ **Setup Automated Checks with Cron**

### **Step 1: Edit Crontab**

```bash
crontab -e
```

### **Step 2: Add Schedule**

Add one of these lines (choose your preferred schedule):

```bash
# Check 3 times daily (9am, 3pm, 9pm)
0 9,15,21 * * * /FULL/PATH/TO/PROJECT/scripts/daily_monitor.sh >> /FULL/PATH/TO/PROJECT/logs/cron.log 2>&1

# Check once daily (9am)
0 9 * * * /FULL/PATH/TO/PROJECT/scripts/daily_monitor.sh >> /FULL/PATH/TO/PROJECT/logs/cron.log 2>&1

# Check every 6 hours
0 */6 * * * /FULL/PATH/TO/PROJECT/scripts/daily_monitor.sh >> /FULL/PATH/TO/PROJECT/logs/cron.log 2>&1
```

**Important:** Replace `/FULL/PATH/TO/PROJECT` with your actual project path (e.g., `/home/username/Projects/Betting Expert Advisor`)!

### **Step 3: Verify Cron Setup**

```bash
# List your cron jobs
crontab -l

# Check cron service is running
systemctl status cron
```

---

## 🎯 **Manual Monitoring Commands**

### **Check All Leagues (Recommended)**
```bash
python scripts/multi_league_tracker.py --once
```

### **Check Specific Leagues**
```bash
# Premier League only
python scripts/multi_league_tracker.py --once --leagues soccer_epl

# Multiple leagues
python scripts/multi_league_tracker.py --once --leagues soccer_epl soccer_spain_la_liga soccer_germany_bundesliga
```

### **Continuous Monitoring**
```bash
# Check every hour (default)
python scripts/multi_league_tracker.py

# Check every 30 minutes
python scripts/multi_league_tracker.py --interval 1800
```

---

## 📊 **Available Leagues**

The system supports these leagues from TheOddsAPI:

| League Key | Competition |
|------------|-------------|
| `soccer_epl` | Premier League (England) |
| `soccer_spain_la_liga` | La Liga (Spain) |
| `soccer_germany_bundesliga` | Bundesliga (Germany) |
| `soccer_italy_serie_a` | Serie A (Italy) |
| `soccer_france_ligue_one` | Ligue 1 (France) |
| `soccer_uefa_champs_league` | UEFA Champions League |
| `soccer_uefa_europa_league` | UEFA Europa League |

---

## 📝 **Log Management**

### **Log Locations**

- **Daily checks:** `logs/daily_checks/`
- **Cron output:** `logs/cron.log`
- **Opportunities:** `multi_league_opportunities.json`

### **Clean Old Logs**

```bash
# Delete logs older than 30 days
find logs/daily_checks/ -name "*.log" -mtime +30 -delete

# Keep only last 100 log files
ls -t logs/daily_checks/*.log | tail -n +101 | xargs rm -f
```

---

## 🔔 **Email Notifications (Optional)**

To get email alerts when opportunities are found:

### **Step 1: Install mailutils**
```bash
sudo apt-get install mailutils
```

### **Step 2: Configure SMTP**

Edit `/etc/mail.rc` or use a service like SendGrid, Mailgun, etc.

### **Step 3: Add to daily_monitor.sh**

Uncomment the email section in `scripts/daily_monitor.sh`:

```bash
# Send email if opportunities found
if grep -q "Total opportunities found: [1-9]" "$LOG_DIR/opportunities_$TIMESTAMP.log"; then
    mail -s "Betting Opportunities Found!" your@email.com < "$LOG_DIR/opportunities_$TIMESTAMP.log"
fi
```

---

## 🔍 **Monitoring System Health**

### **Check if cron is working**
```bash
# View cron log
tail -f logs/cron.log

# Check recent daily check logs
ls -lht logs/daily_checks/ | head -10
```

### **Test the daily monitor script**
```bash
# Run manually to test
./scripts/daily_monitor.sh
```

### **Check API usage**
```bash
# See remaining API calls
python -c "from src.adapters.theodds_api import TheOddsAPIAdapter; from src.config import settings; adapter = TheOddsAPIAdapter(api_key=settings.THEODDS_API_KEY); print(f'Remaining: {adapter._get_remaining_requests()}')"
```

---

## 🎯 **Recommended Schedule**

For optimal monitoring with a 500 request/month API quota:

### **Conservative (150 requests/month)**
- 3 checks per day
- 5 leagues per check
- = 15 requests/day × 30 days = 450 requests/month
- Leaves buffer for manual checks

```bash
# Add to crontab
0 9,15,21 * * * cd /path/to/project && ./scripts/daily_monitor.sh >> logs/cron.log 2>&1
```

### **Aggressive (450 requests/month)**
- 5 checks per day
- 3 leagues per check
- = 15 requests/day × 30 days = 450 requests/month

```bash
# Add to crontab
0 6,10,14,18,22 * * * cd /path/to/project && ./scripts/daily_monitor.sh >> logs/cron.log 2>&1
```

---

## 📱 **Mobile Notifications (Advanced)**

For push notifications to your phone:

### **Option 1: Pushover**
1. Create account at https://pushover.net ($5 one-time)
2. Install app on phone
3. Add to `daily_monitor.sh`:

```bash
curl -s \
  --form-string "token=YOUR_APP_TOKEN" \
  --form-string "user=YOUR_USER_KEY" \
  --form-string "message=Betting opportunities found!" \
  https://api.pushover.net/1/messages.json
```

### **Option 2: Telegram**
1. Create Telegram bot via @BotFather
2. Get chat ID
3. Add to `daily_monitor.sh`:

```bash
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_CHAT_ID="your_chat_id"
MESSAGE="Betting opportunities found!"

curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHAT_ID}" \
  -d text="${MESSAGE}"
```

---

## 🔧 **Troubleshooting**

### **Cron not running**
```bash
# Check cron service
sudo systemctl status cron

# Restart cron
sudo systemctl restart cron

# Check for errors
grep CRON /var/log/syslog
```

### **Script permission errors**
```bash
# Make script executable
chmod +x scripts/daily_monitor.sh

# Check file permissions
ls -l scripts/daily_monitor.sh
```

### **Python import errors in cron**
Make sure cron job includes full path and activates venv:
```bash
0 9 * * * /FULL/PATH/TO/PROJECT/scripts/daily_monitor.sh
```

---

## 📈 **Optimization Tips**

1. **API Efficiency**
   - Use caching (already implemented)
   - Group league checks together
   - Avoid checking during low-activity hours (2-6 AM)

2. **Performance**
   - Schedule checks when odds change most (near match times)
   - Focus on leagues you actually want to bet on
   - Use `--leagues` flag to check specific leagues

3. **Storage**
   - Rotate logs weekly/monthly
   - Archive old opportunities
   - Compress large log files

---

## ✅ **Quick Setup Checklist**

- [ ] Test daily monitor script manually: `./scripts/daily_monitor.sh`
- [ ] Add cron job with desired schedule
- [ ] Verify cron is running: `crontab -l`
- [ ] Check logs are being created: `ls logs/daily_checks/`
- [ ] Set up log rotation
- [ ] (Optional) Configure email/push notifications
- [ ] Monitor API usage weekly
- [ ] Review found opportunities regularly

---

## 🎯 **Expected Results**

With proper setup:
- ✅ Automated daily checks run silently
- ✅ Logs capture all activity
- ✅ Opportunities saved to JSON
- ✅ Email/notifications on value bets
- ✅ System monitors 5-7 leagues continuously
- ✅ API quota managed efficiently

**You'll find 0-5 value bets per week on average** (markets are efficient!).

---

*Last updated: October 28, 2025*
