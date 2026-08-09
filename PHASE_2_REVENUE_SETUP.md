# Phase 2: Revenue Streams Setup (Weeks 5-8)
## Avoltium.in - Complete Revenue Implementation Guide

---

## 🎯 Revenue Targets

**Goals for Phase 2:**
- Launch 3 subscription tiers
- First 100 paying customers
- $5,000-10,000 MRR by end of phase
- Premium features operational

---

## Revenue Streams Overview

### 1. Subscription Plans (Primary)

#### Tier 1: Starter - $9/month
**Target:** Individuals, side hustlers
- 10 articles/month (AI generated)
- Basic image sourcing
- Email support
- Community access
- **Setup effort:** 2 days

#### Tier 2: Pro - $29/month
**Target:** Content creators, small agencies
- 50 articles/month
- Advanced image sourcing (WebP, multiple sizes)
- SEO optimization tools (keyword analysis)
- Priority support
- Custom branding on exports
- **Setup effort:** 4 days

#### Tier 3: Enterprise - $99/month
**Target:** Agencies, large publishers
- Unlimited articles
- API access (for integrations)
- Custom AI model fine-tuning
- Dedicated success manager
- Bulk processing (500+ articles)
- **Setup effort:** 5 days

---

## 2. Implementation Roadmap

### Week 5: Billing Infrastructure

#### 5.1 Stripe Integration Setup
```bash
# Install Stripe SDK
pip install stripe

# Create Stripe account
# Visit: https://dashboard.stripe.com
```

**Create `billing_service.py`:**
```python
import stripe
import os

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def create_customer(email, name):
    """Create Stripe customer"""
    customer = stripe.Customer.create(
        email=email,
        name=name
    )
    return customer.id

def create_subscription(customer_id, price_id):
    """Create monthly subscription"""
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"],
    )
    return subscription

def cancel_subscription(subscription_id):
    """Cancel subscription at period end"""
    stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=True,
    )
    return True
```

#### 5.2 Define Stripe Products & Prices
```python
# Create products (one-time)
products = {
    "starter": stripe.Product.create(
        name="Starter Plan",
        description="10 articles/month"
    ),
    "pro": stripe.Product.create(
        name="Pro Plan",
        description="50 articles/month + SEO tools"
    ),
    "enterprise": stripe.Product.create(
        name="Enterprise Plan",
        description="Unlimited + API access"
    )
}

# Create prices (monthly)
prices = {
    "starter": stripe.Price.create(
        product=products["starter"].id,
        unit_amount=900,  # $9.00
        currency="usd",
        recurring={"interval": "month"}
    ),
    "pro": stripe.Price.create(
        product=products["pro"].id,
        unit_amount=2900,  # $29.00
        currency="usd",
        recurring={"interval": "month"}
    ),
    "enterprise": stripe.Price.create(
        product=products["enterprise"].id,
        unit_amount=9900,  # $99.00
        currency="usd",
        recurring={"interval": "month"}
    )
}
```

#### 5.3 WordPress Payment Integration
**Plugin:** `avoltium-billing.php`
```php
<?php
/**
 * Plugin Name: Avoltium Billing
 * Description: Stripe subscription management
 */

// Handle subscription webhooks
add_action('rest_api_init', function() {
    register_rest_route('avoltium/v1', '/subscribe', array(
        'methods' => 'POST',
        'callback' => 'handle_subscription',
        'permission_callback' => 'is_user_logged_in'
    ));
});

function handle_subscription($request) {
    $plan = $request->get_param('plan');
    $user_id = get_current_user_id();
    
    // Create Stripe customer
    $customer_id = create_stripe_customer($user_id);
    
    // Create subscription
    $subscription = stripe_create_subscription($customer_id, $plan);
    
    // Store in user meta
    update_user_meta($user_id, '_stripe_customer_id', $customer_id);
    update_user_meta($user_id, '_stripe_subscription_id', $subscription->id);
    
    return rest_ensure_response([
        'success' => true,
        'subscription_id' => $subscription->id
    ]);
}
```

### Week 6: Feature Gating & Metering

#### 6.1 Create User Tier System
```python
class UserTierManager:
    """Manage user subscription tiers"""
    
    TIER_LIMITS = {
        'free': {'articles': 0, 'images': 0},
        'starter': {'articles': 10, 'images': 10},
        'pro': {'articles': 50, 'images': 50},
        'enterprise': {'articles': 999999, 'images': 999999}
    }
    
    @staticmethod
    def get_user_tier(user_id):
        """Get user's current tier from WordPress"""
        tier = get_user_meta(user_id, '_subscription_tier', true)
        return tier or 'free'
    
    @staticmethod
    def get_usage(user_id, metric):
        """Get current month usage"""
        from datetime import datetime, timedelta
        month_start = datetime.now().replace(day=1)
        
        usage = get_user_meta(user_id, f'_usage_{metric}_month', true)
        last_reset = get_user_meta(user_id, '_usage_reset', true)
        
        # Reset if new month
        if not last_reset or datetime.fromisoformat(last_reset) < month_start:
            update_user_meta(user_id, f'_usage_{metric}_month', 0)
            update_user_meta(user_id, '_usage_reset', datetime.now().isoformat())
            return 0
        
        return int(usage) if usage else 0
    
    @staticmethod
    def increment_usage(user_id, metric):
        """Track usage"""
        current = UserTierManager.get_usage(user_id, metric)
        update_user_meta(user_id, f'_usage_{metric}_month', current + 1)
    
    @staticmethod
    def can_generate(user_id):
        """Check if user can generate articles"""
        tier = UserTierManager.get_user_tier(user_id)
        limit = UserTierManager.TIER_LIMITS[tier]['articles']
        usage = UserTierManager.get_usage(user_id, 'articles')
        
        if limit == 999999:  # Enterprise
            return True
        return usage < limit
```

#### 6.2 Integrate Gating into generate_article.py
```python
from avoltium_billing import UserTierManager

def generate_article_with_limits(user_id, topic):
    """Generate article with tier limits"""
    
    # Check usage limits
    if not UserTierManager.can_generate(user_id):
        return {
            'error': 'Monthly limit reached',
            'tier': UserTierManager.get_user_tier(user_id),
            'upgrade_url': '/pricing/'
        }
    
    # Generate article
    article = generate_article(topic)
    
    # Track usage
    UserTierManager.increment_usage(user_id, 'articles')
    
    return {'success': True, 'article': article}
```

### Week 7: Premium Features

#### 7.1 AI Image Generation Service
**Feature:** DALL-E / Stable Diffusion integration

```python
import requests
import os

class ImageGenerationService:
    """Premium image generation"""
    
    API_KEY = os.getenv('OPENAI_API_KEY')
    API_URL = "https://api.openai.com/v1/images/generations"
    
    @staticmethod
    def generate_image(prompt, size="1024x1024"):
        """Generate image from prompt"""
        headers = {
            "Authorization": f"Bearer {ImageGenerationService.API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": "hd"
        }
        
        response = requests.post(
            ImageGenerationService.API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['data'][0]['url']
        
        return None
    
    @staticmethod
    def generate_for_article(article_content):
        """Generate image for article"""
        # Extract key topic
        topics = article_content[:200].split()[:5]
        prompt = f"Professional {' '.join(topics)} illustration, high quality, modern design"
        
        return ImageGenerationService.generate_image(prompt)
```

#### 7.2 SEO Analysis Tool
```python
class SEOAnalysisTool:
    """Integrated SEO analysis"""
    
    @staticmethod
    def analyze_article(title, content, url):
        """Analyze SEO metrics"""
        from avoltium.token_cache import get_cache
        
        # Get from cache if available
        cache = get_cache()
        cache_key = f"seo_analysis:{url}"
        cached = cache.get_cached_content(cache_key, {})
        if cached:
            return json.loads(cached)
        
        analysis = {
            'title_length': len(title),
            'content_length': len(content),
            'word_count': len(content.split()),
            'readability_score': calculate_readability(content),
            'keyword_density': analyze_keywords(content),
            'meta_suggestions': generate_meta_tags(title, content)
        }
        
        # Cache results
        cache.cache_content(cache_key, json.dumps(analysis), {}, ttl_days=30)
        
        return analysis
```

### Week 8: Launch & Validation

#### 8.1 Create Pricing Page
**WordPress Page:** `/pricing/`

```html
<div class="pricing-section">
  <div class="pricing-card starter">
    <h3>Starter</h3>
    <p class="price">$9/month</p>
    <ul>
      <li>10 articles/month</li>
      <li>Basic image sourcing</li>
      <li>Email support</li>
    </ul>
    <button onclick="subscribe('starter')">Get Started</button>
  </div>
  
  <div class="pricing-card pro featured">
    <span class="badge">Most Popular</span>
    <h3>Pro</h3>
    <p class="price">$29/month</p>
    <ul>
      <li>50 articles/month</li>
      <li>Advanced image sourcing</li>
      <li>SEO analysis tools</li>
      <li>Priority support</li>
    </ul>
    <button onclick="subscribe('pro')">Get Started</button>
  </div>
  
  <div class="pricing-card enterprise">
    <h3>Enterprise</h3>
    <p class="price">$99/month</p>
    <ul>
      <li>Unlimited articles</li>
      <li>API access</li>
      <li>Custom AI training</li>
      <li>Dedicated manager</li>
    </ul>
    <button onclick="subscribe('enterprise')">Contact Us</button>
  </div>
</div>
```

#### 8.2 Email Marketing Setup
**SendGrid Integration**

```python
import sendgrid
from sendgrid.helpers.mail import Mail

class EmailService:
    """Transactional & marketing emails"""
    
    SG = sendgrid.SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
    
    @staticmethod
    def send_welcome(email, name, plan):
        """Welcome email to new subscriber"""
        message = Mail(
            from_email='welcome@avoltium.in',
            to_emails=email,
            subject=f'Welcome to Avoltium {plan.title()}!',
            html_content=f'''
            <h1>Welcome {name}!</h1>
            <p>Your {plan} subscription is now active.</p>
            <p><a href="/dashboard/">Go to Dashboard</a></p>
            '''
        )
        try:
            response = EmailService.SG.send(message)
            return response.status_code == 202
        except Exception as e:
            print(f"Email error: {e}")
            return False
    
    @staticmethod
    def send_daily_digest(user_id):
        """Daily digest of generated articles"""
        # Get user's articles from today
        articles = get_user_articles(user_id, days=1)
        
        html = "<h2>Your Articles Today</h2><ul>"
        for article in articles:
            html += f"<li><a href='{article['url']}'>{article['title']}</a></li>"
        html += "</ul>"
        
        message = Mail(
            from_email='digest@avoltium.in',
            to_emails=get_user_email(user_id),
            subject='Your Daily Digest',
            html_content=html
        )
        
        return EmailService.SG.send(message).status_code == 202
```

#### 8.3 Dashboard Updates
**Show:**
- Current usage vs. limits
- Next billing date
- Upgrade recommendations
- Premium feature trials
- Analytics & insights

---

## 3. Success Metrics

### Week 5 Goals
- [ ] Stripe account configured
- [ ] Payment processing working
- [ ] 5 test transactions successful

### Week 6 Goals
- [ ] Feature gating deployed
- [ ] Tier system tracking usage
- [ ] No limit bypass exploits

### Week 7 Goals
- [ ] Premium features operational
- [ ] Image generation working
- [ ] SEO analysis tool live

### Week 8 Goals
- [ ] 100+ signups
- [ ] $5k+ MRR
- [ ] <1% churn rate
- [ ] >90% usage satisfaction

---

## 4. Financial Projections

### Conservative (Month 6)
- Starter: 50 users @ $9 = $450
- Pro: 30 users @ $29 = $870
- Enterprise: 5 users @ $99 = $495
- **Monthly Revenue: $1,815**

### Moderate (Month 6)
- Starter: 100 users @ $9 = $900
- Pro: 75 users @ $29 = $2,175
- Enterprise: 15 users @ $99 = $1,485
- **Monthly Revenue: $4,560**

### Optimistic (Month 6)
- Starter: 200 users @ $9 = $1,800
- Pro: 150 users @ $29 = $4,350
- Enterprise: 30 users @ $99 = $2,970
- **Monthly Revenue: $9,120**

---

## 5. Retention Strategy

### Email Nurture Sequence
1. **Day 0:** Welcome email
2. **Day 3:** First article guide
3. **Day 7:** Tips for success
4. **Day 14:** Feature announcement
5. **Day 30:** Upgrade offer
6. **Day 60:** Usage check-in

### In-App Notifications
- Welcome message
- Feature tips
- Usage alerts (80% of limit)
- Expiring trial reminder
- Upgrade suggestions

### Customer Support
- Email support within 24h
- FAQ page
- Video tutorials
- Feature requests voting

---

## 6. Testing Checklist

- [ ] Stripe webhooks tested
- [ ] Payment flow tested end-to-end
- [ ] Refund process tested
- [ ] Feature gating prevents overage
- [ ] Email notifications working
- [ ] Dashboard shows correct limits
- [ ] Upgrade flow smooth
- [ ] Cancel flow works

---

## 7. Launch Checklist

- [ ] Pricing page live
- [ ] Payment processing ready
- [ ] Feature gating deployed
- [ ] Email system configured
- [ ] Support process ready
- [ ] Terms of Service updated
- [ ] Privacy Policy updated
- [ ] Stripe account verified
- [ ] Test cards working
- [ ] Analytics tracking

---

## Next Phase: Phase 3 (Weeks 9-16)

After revenue validation:
- Premium features expansion
- AI image generation service
- Advanced SEO tools
- Bulk processing
- API program launch

---

**Expected Outcome:** $5k-10k MRR by end of Phase 2
**Target Customers:** 100-150 paid users
**Churn Rate Target:** <2% monthly
**NPS Target:** >40

---

*Phase 2 Timeline: August 23 - September 20, 2026*
