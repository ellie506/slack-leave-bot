# Slack Leave Management Bot 🏖️

A fully functional Slack bot for managing employee leave requests, approvals/declines, and generating records.

## Features

✅ **Leave Requests** - Employees can request leave through `/leave` command
✅ **Approval Workflow** - Managers receive requests with approve/decline buttons
✅ **Leave Balances** - Track annual, sick, and personal leave balances
✅ **Record Keeping** - All requests stored in SQLite database
✅ **Reports** - Generate leave reports with `/leave-report` command
✅ **Business Days** - Automatically calculates business days (excludes weekends)

## Setup Instructions

### 1. Create a Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name it "Leave Bot" and select your workspace
4. Click **"Create App"**

### 2. Configure Bot Permissions

Go to **OAuth & Permissions** and add these Bot Token Scopes:
- `chat:write` - Send messages
- `commands` - Enable slash commands
- `users:read` - Read user information
- `im:write` - Send DMs

### 3. Create Slash Commands

Go to **Slash Commands** and create these commands:

**Command 1: /leave**
- Command: `/leave`
- Request URL: `https://your-domain.com/slack/events`
- Short Description: `Request time off`
- Usage Hint: `Request leave`

**Command 2: /leave-balance**
- Command: `/leave-balance`
- Request URL: `https://your-domain.com/slack/events`
- Short Description: `Check your leave balance`

**Command 3: /leave-report**
- Command: `/leave-report`
- Request URL: `https://your-domain.com/slack/events`
- Short Description: `Generate leave report (managers)`

### 4. Enable Interactivity

1. Go to **Interactivity & Shortcuts**
2. Turn on Interactivity
3. Set Request URL: `https://your-domain.com/slack/events`
4. Click **Save Changes**

### 5. Install to Workspace

1. Go to **OAuth & Permissions**
2. Click **"Install to Workspace"**
3. Authorize the app
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 6. Get Your Signing Secret

1. Go to **Basic Information**
2. Under **App Credentials**, find **Signing Secret**
3. Click **Show** and copy it

### 7. Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```
   SLACK_BOT_TOKEN=xoxb-your-token-here
   SLACK_SIGNING_SECRET=your-secret-here
   ```

### 8. Install Dependencies

```bash
pip install -r requirements.txt
```

### 9. Run the Bot

```bash
python app.py
```

The bot will start on `http://localhost:3000`

### 10. Expose to Internet (for Development)

Use ngrok to expose your local server:

```bash
ngrok http 3000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`) and update:
- Slash Commands Request URLs
- Interactivity Request URL

Replace `https://your-domain.com` with your ngrok URL + `/slack/events`

## Usage

### Request Leave

1. Type `/leave` in any Slack channel or DM
2. Fill out the form:
   - Select leave type (Annual, Sick, Personal)
   - Choose start and end dates
   - Add reason (optional)
   - Select your manager
3. Click **Submit**

Your manager will receive a notification with approve/decline buttons.

### Check Leave Balance

Type `/leave-balance` to see your remaining leave days:
- Annual Leave
- Sick Leave  
- Personal Leave

### View Leave Report

Type `/leave-report` to see recent leave requests across the team (useful for managers/HR).

## Database Schema

### leave_requests
- `id` - Auto-incrementing primary key
- `user_id` - Slack user ID
- `user_name` - Employee name
- `leave_type` - annual, sick, or personal
- `start_date` - Leave start date
- `end_date` - Leave end date
- `days` - Number of business days
- `reason` - Optional reason
- `status` - pending, approved, or declined
- `manager_id` - Manager's Slack user ID
- `manager_name` - Manager's name
- `requested_at` - Timestamp of request
- `responded_at` - Timestamp of approval/decline

### leave_balances
- `user_id` - Slack user ID (primary key)
- `user_name` - Employee name
- `annual_leave` - Remaining annual leave days (default: 20)
- `sick_leave` - Remaining sick leave days (default: 10)
- `personal_leave` - Remaining personal leave days (default: 5)
- `updated_at` - Last update timestamp

## Deployment

### Production Deployment Options

**Option 1: Heroku**
```bash
heroku create your-leave-bot
git push heroku main
heroku config:set SLACK_BOT_TOKEN=xoxb-your-token
heroku config:set SLACK_SIGNING_SECRET=your-secret
```

**Option 2: Railway**
```bash
railway login
railway init
railway up
railway variables set SLACK_BOT_TOKEN=xoxb-your-token
railway variables set SLACK_SIGNING_SECRET=your-secret
```

**Option 3: AWS/Google Cloud/Azure**
Deploy as a containerized application or serverless function.

Remember to update your Slack app's Request URLs with your production domain!

## Customization

### Adjust Default Leave Balances

Edit the `CREATE TABLE` statement in `init_db()`:
```python
annual_leave INTEGER DEFAULT 20,  # Change this
sick_leave INTEGER DEFAULT 10,    # Change this
personal_leave INTEGER DEFAULT 5  # Change this
```

### Add More Leave Types

Add to the leave type options in the modal and update the column map in helper functions.

### Add Notifications

Integrate with calendar systems (Google Calendar, Outlook) or send email notifications.

## Troubleshooting

**Bot doesn't respond to commands:**
- Check if Request URLs are correct
- Verify bot is running and accessible
- Check ngrok tunnel is active (for local dev)
- Review Slack app logs

**Permission errors:**
- Verify bot token scopes in OAuth & Permissions
- Reinstall app to workspace if scopes changed

**Database errors:**
- Ensure `leave_records.db` has write permissions
- Check SQLite is installed

## Future Enhancements

- [ ] Export reports to CSV/Excel
- [ ] Calendar integrations (Google Calendar, Outlook)
- [ ] Email notifications
- [ ] Admin dashboard
- [ ] Leave policies (e.g., blackout dates)
- [ ] Multi-level approval workflows
- [ ] Integration with HRIS systems
- [ ] Team calendar view
- [ ] Conflict detection (overlapping leave)

## Support

For issues or questions, check the Slack API documentation: https://api.slack.com/docs

## License

MIT License - Feel free to modify and use for your organization!
