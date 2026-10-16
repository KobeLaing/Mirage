# Mirage

A social platform where people post images and videos they suspect are
AI-generated, and the community votes: **AI** or **Real**. Voting earns XP,
XP earns verifier ranks (Bronze → Silver → Gold → Platinum → Palladium), and
ranks show as medals.

It's a local side project, built with a secure SDLC so it can grow without
a rewrite:


## Features

- **Sign-in**: username and password, Argon2id hashes, a signed httpOnly
  session cookie, CSRF protection, login rate limits, and a honeypot field
  for bots. Every page except `/login` requires a signed-in user.
  
- **Feed and profiles**: post images or videos, vote AI/Real (+10 XP), post
  (+20 XP), react, and **comment** (no XP).
  (Point system has not been designed properly yet)
  
- **Left side pane** on the feed and profile pages:
  1. **Leaderboard**: top 50 by XP, with your row highlighted.
  2. **Blind Mode**: hides vote counts, results and comments until you vote.
     Enforced by the API, not just hidden in the browser.
  3. **AI Authenticity Scanner**: privately check an image or video for signs
     of AI generation. Runs locally; the file is deleted after the scan.

