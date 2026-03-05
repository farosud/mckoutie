"""
Data-driven country landing pages for mckoutie.

Each country gets a localized page at /{COUNTRY_CODE} with:
- Cultural copy and local startup references
- Flag-inspired accent colors
- Unsplash hero image representing the country
- All in English (except AR which is handled separately in server.py)
"""

COUNTRIES = {
    "MX": {
        "name": "Mexico",
        "lang": "en",
        "accent": "#006847",
        "accent2": "#CE1126",
        "flag_colors": ["#006847", "#fff", "#CE1126"],
        "image": "https://images.unsplash.com/photo-1585464231875-d9ef1f5ad396?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Mexico — Growth consulting for Mexican startups",
        "meta": "AI-powered traction analysis for Mexican startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Mexican startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No BS, no bloated decks. $39/mo.",
        "startups": "Kavak, Clip, Bitso, Konfio, Stori",
        "ecosystem_name": "Mexican startup ecosystem",
        "ecosystem_desc": "Mexico is Latin America's second-largest economy with a booming tech scene. The talent is world-class — what separates the winners from the rest is distribution strategy.",
        "market_context": "Whether you're targeting the Mexican market, going after LATAM, or building for the US from Mexico City — the analysis adapts. If your play is fintech for the unbanked, we'll tell you. If it's B2B SaaS for US SMBs, we'll show you the path.",
        "pricing_objection": "A decent consultant charges $39 per hour. Here you get a complete analysis that updates monthly. A McKinsey engagement costs $100K+ for something worse.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with tacos and tequila.",
    },
    "BR": {
        "name": "Brazil",
        "lang": "en",
        "accent": "#009739",
        "accent2": "#FEDD00",
        "flag_colors": ["#009739", "#FEDD00", "#002776"],
        "image": "https://images.unsplash.com/photo-1483729558449-99ef09a8c325?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Brazil — Growth consulting for Brazilian startups",
        "meta": "AI-powered traction analysis for Brazilian startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Brazilian startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No fluff, no corporate theater. $39/mo.",
        "startups": "Nubank, iFood, VTEX, Creditas, Loft",
        "ecosystem_name": "Brazilian startup ecosystem",
        "ecosystem_desc": "Brazil is the largest tech market in Latin America. Home to more unicorns than the rest of the region combined. The talent is exceptional — the bottleneck is always distribution.",
        "market_context": "Whether you're building for Brazil's 200M+ consumers, expanding across LATAM, or targeting the US market from Sao Paulo — the analysis adapts. WhatsApp commerce, Pix-native fintech, or global SaaS — we've got you.",
        "pricing_objection": "A decent consultant charges $39 per hour. Here you get a complete analysis that updates monthly. A McKinsey engagement costs $100K+ for something worse.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with acai and code.",
    },
    "CO": {
        "name": "Colombia",
        "lang": "en",
        "accent": "#FCD116",
        "accent2": "#003893",
        "flag_colors": ["#FCD116", "#003893", "#CE1126"],
        "image": "https://images.unsplash.com/photo-1568632234157-ce7aecd03d0d?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Colombia — Growth consulting for Colombian startups",
        "meta": "AI-powered traction analysis for Colombian startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Colombian startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No humo, no fluff. $39/mo.",
        "startups": "Rappi, Platzi, Truora, Addi, Bold",
        "ecosystem_name": "Colombian startup ecosystem",
        "ecosystem_desc": "Colombia is one of Latin America's fastest-growing tech hubs. Bogota and Medellin are producing world-class startups. The talent is there — the missing piece is a growth playbook.",
        "market_context": "Whether you're building for the Colombian market, scaling across the Andean region, or going global from Bogota — the analysis adapts to your reality.",
        "pricing_objection": "A decent consultant charges $39 per hour. Here you get a complete analysis that updates monthly. Skip the overpriced agencies.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with tinto and parce energy.",
    },
    "CL": {
        "name": "Chile",
        "lang": "en",
        "accent": "#D52B1E",
        "accent2": "#0039A6",
        "flag_colors": ["#D52B1E", "#fff", "#0039A6"],
        "image": "https://images.unsplash.com/photo-1536708880921-03a9306ec47d?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Chile — Growth consulting for Chilean startups",
        "meta": "AI-powered traction analysis for Chilean startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Chilean startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. Straight talk, no corporate fluff. $39/mo.",
        "startups": "Cornershop, NotCo, Betterfly, Fintual, Buk",
        "ecosystem_name": "Chilean startup ecosystem",
        "ecosystem_desc": "Chile punches way above its weight in startups. Start-Up Chile put the country on the map, and the ecosystem hasn't stopped growing. World-class founders, stable economy — distribution is the game.",
        "market_context": "Whether you're building for Chile, expanding to the Southern Cone, or targeting global markets from Santiago — the analysis adapts to your specific situation.",
        "pricing_objection": "A decent consultant charges $39 per hour. Here you get a complete analysis that updates monthly. No need for overpriced consulting firms.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with pisco and persistence.",
    },
    "PE": {
        "name": "Peru",
        "lang": "en",
        "accent": "#D91023",
        "accent2": "#fff",
        "flag_colors": ["#D91023", "#fff", "#D91023"],
        "image": "https://images.unsplash.com/photo-1526392060635-9d6019884377?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Peru — Growth consulting for Peruvian startups",
        "meta": "AI-powered traction analysis for Peruvian startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Peruvian startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. Real strategy, not generic advice. $39/mo.",
        "startups": "Crehana, Keynua, Chazki, Culqi, Favo",
        "ecosystem_name": "Peruvian startup ecosystem",
        "ecosystem_desc": "Peru's startup scene is maturing fast. Lima is becoming a serious tech hub with strong fintech and edtech verticals. The founders are hungry — they just need the right growth playbook.",
        "market_context": "Whether you're targeting Peru's growing digital economy, the Andean markets, or building for global scale from Lima — the analysis adapts.",
        "pricing_objection": "A decent consultant charges $39 per hour. Here you get a complete analysis that updates monthly.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with ceviche and conviction.",
    },
    "UY": {
        "name": "Uruguay",
        "lang": "en",
        "accent": "#001489",
        "accent2": "#FCD116",
        "flag_colors": ["#001489", "#fff", "#FCD116"],
        "image": "https://images.unsplash.com/photo-1601996759367-3e5a836fedf3?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Uruguay — Growth consulting for Uruguayan startups",
        "meta": "AI-powered traction analysis for Uruguayan startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Uruguayan startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No nonsense. $39/mo.",
        "startups": "dLocal, GeneXus, Tryolabs, Pedidos Ya, Infocorp",
        "ecosystem_name": "Uruguayan startup ecosystem",
        "ecosystem_desc": "Uruguay is the quiet powerhouse of LATAM tech. Highest per-capita startup density in the region, incredible talent pool, and dLocal proved Uruguayan startups can go global. The edge? Strategy.",
        "market_context": "Whether you're building from Montevideo for the Southern Cone, LATAM, or global markets — the analysis adapts. Uruguay's small market means you're probably already thinking international.",
        "pricing_objection": "For the cost of one hour with a consultant, you get a full analysis updated monthly.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with mate and ambition.",
    },
    "UK": {
        "name": "United Kingdom",
        "lang": "en",
        "accent": "#012169",
        "accent2": "#C8102E",
        "flag_colors": ["#012169", "#fff", "#C8102E"],
        "image": "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie UK — Growth consulting for British startups",
        "meta": "AI-powered traction analysis for UK startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for British startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No waffle, no consultancy theatre. $39/mo.",
        "startups": "Revolut, Monzo, Deliveroo, Wise, Checkout.com",
        "ecosystem_name": "UK startup ecosystem",
        "ecosystem_desc": "London is Europe's undisputed startup capital. The UK produces more unicorns than any other European country. But competition is fierce — the difference between scaling and stalling is knowing which growth channel to bet on.",
        "market_context": "Whether you're targeting the UK market, expanding across Europe, or building for global scale from London — the analysis adapts to your specific context and competitive landscape.",
        "pricing_objection": "A decent consultant charges more than $39 per hour. Here you get a complete analysis that updates monthly. A Big Four engagement costs six figures for something worse.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with tea and tenacity.",
    },
    "DE": {
        "name": "Germany",
        "lang": "en",
        "accent": "#DD0000",
        "accent2": "#FFCC00",
        "flag_colors": ["#000", "#DD0000", "#FFCC00"],
        "image": "https://images.unsplash.com/photo-1560969184-10fe8719e047?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Germany — Growth consulting for German startups",
        "meta": "AI-powered traction analysis for German startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for German startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No Berater-Bullshit. $39/mo.",
        "startups": "Celonis, N26, FlixBus, Trade Republic, Personio",
        "ecosystem_name": "German startup ecosystem",
        "ecosystem_desc": "Germany is Europe's largest economy and Berlin is one of the world's top startup cities. German engineering meets startup speed — but even the best products die without the right distribution strategy.",
        "market_context": "Whether you're building for the DACH market, expanding across Europe, or going global from Berlin or Munich — the analysis adapts. B2B SaaS, deep tech, or marketplace — we cover it all.",
        "pricing_objection": "A decent consultant charges more per hour than this costs per month. Here you get a complete analysis that updates every month.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with precision and pretzels.",
    },
    "FR": {
        "name": "France",
        "lang": "en",
        "accent": "#002395",
        "accent2": "#ED2939",
        "flag_colors": ["#002395", "#fff", "#ED2939"],
        "image": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie France — Growth consulting for French startups",
        "meta": "AI-powered traction analysis for French startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for French startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No corporate theatre. $39/mo.",
        "startups": "BlaBlaCar, Doctolib, Contentsquare, Qonto, Alan",
        "ecosystem_name": "French startup ecosystem",
        "ecosystem_desc": "France has become Europe's startup darling. La French Tech initiative, Station F, and a wave of unicorns have put Paris on par with London and Berlin. The founders are brilliant — the growth playbook is what makes the difference.",
        "market_context": "Whether you're building for the French market, the Francophone world, or going global from Paris — the analysis adapts to your competitive landscape.",
        "pricing_objection": "A decent consultant charges more per hour than this costs per month. Skip the overpriced consulting firms.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with croissants and conviction.",
    },
    "ES": {
        "name": "Spain",
        "lang": "en",
        "accent": "#AA151B",
        "accent2": "#F1BF00",
        "flag_colors": ["#AA151B", "#F1BF00", "#AA151B"],
        "image": "https://images.unsplash.com/photo-1543783207-ec64e4d95325?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Spain — Growth consulting for Spanish startups",
        "meta": "AI-powered traction analysis for Spanish startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Spanish startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No humo, no consultancy theatre. $39/mo.",
        "startups": "Glovo, Cabify, Wallbox, Jobandtalent, Factorial",
        "ecosystem_name": "Spanish startup ecosystem",
        "ecosystem_desc": "Spain's startup scene is booming. Barcelona and Madrid are attracting global talent, and Spanish founders have a unique advantage — a direct bridge to the massive LATAM market. The winning move? Knowing exactly which growth channel to bet on.",
        "market_context": "Whether you're building for Spain, the broader Hispanic market, or going global from Barcelona or Madrid — the analysis adapts. Your Spanish-speaking market of 500M+ people is an unfair advantage if you know how to use it.",
        "pricing_objection": "A decent consultant charges more per hour than this costs per month. Get real strategy, not generic advice.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with paella and purpose.",
    },
    "IT": {
        "name": "Italy",
        "lang": "en",
        "accent": "#008C45",
        "accent2": "#CD212A",
        "flag_colors": ["#008C45", "#fff", "#CD212A"],
        "image": "https://images.unsplash.com/photo-1515542622106-78bda8ba0e5b?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Italy — Growth consulting for Italian startups",
        "meta": "AI-powered traction analysis for Italian startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Italian startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No teatro aziendale. $39/mo.",
        "startups": "Satispay, Scalapay, Bending Spoons, Musixmatch, Yolo Group",
        "ecosystem_name": "Italian startup ecosystem",
        "ecosystem_desc": "Italy is waking up as a startup nation. Milan is leading the charge with fintech and design-tech, while the country's deep expertise in fashion, food, and manufacturing creates unique startup opportunities. The talent is there — the growth strategy is what's missing.",
        "market_context": "Whether you're building for the Italian market, targeting Southern Europe, or going global from Milan — the analysis adapts to your vertical and competitive landscape.",
        "pricing_objection": "A decent consultant charges more per hour than this costs per month. Real strategy beats corporate presentations.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with espresso and elegance.",
    },
    "CA": {
        "name": "Canada",
        "lang": "en",
        "accent": "#FF0000",
        "accent2": "#fff",
        "flag_colors": ["#FF0000", "#fff", "#FF0000"],
        "image": "https://images.unsplash.com/photo-1517935706615-2717063c2225?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Canada — Growth consulting for Canadian startups",
        "meta": "AI-powered traction analysis for Canadian startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Canadian startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No fluff, no corporate theatre. $39/mo.",
        "startups": "Shopify, Wealthsimple, Clio, ApplyBoard, Coveo",
        "ecosystem_name": "Canadian startup ecosystem",
        "ecosystem_desc": "Canada produces world-class startups from coast to coast — Toronto, Vancouver, Montreal, Waterloo. Shopify proved Canadian companies can dominate globally. The ecosystem is mature, the talent is deep — the edge is knowing which growth channel to double down on.",
        "market_context": "Whether you're building for the Canadian market, targeting the US from next door, or going global from Toronto or Vancouver — the analysis adapts. Your proximity to the US market is a massive advantage if you know how to leverage it.",
        "pricing_objection": "A decent consultant charges $39 per hour. Here you get a complete analysis that updates monthly.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with maple syrup and momentum.",
    },
    "PT": {
        "name": "Portugal",
        "lang": "en",
        "accent": "#006600",
        "accent2": "#FF0000",
        "flag_colors": ["#006600", "#FF0000", "#FFC400"],
        "image": "https://images.unsplash.com/photo-1555881400-74d7acaacd8b?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Portugal — Growth consulting for Portuguese startups",
        "meta": "AI-powered traction analysis for Portuguese startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Portuguese startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No filler, just strategy. $39/mo.",
        "startups": "Feedzai, OutSystems, Talkdesk, Unbabel, Anchorage",
        "ecosystem_name": "Portuguese startup ecosystem",
        "ecosystem_desc": "Portugal punches way above its weight. Web Summit moved to Lisbon for a reason. The country is producing unicorns, attracting global talent, and building a bridge between Europe and the Lusophone world. Great founders, incredible quality of life — distribution strategy is the multiplier.",
        "market_context": "Whether you're building for Portugal, the Lusophone markets (Brazil, Africa), or going global from Lisbon — the analysis adapts. Your language connects you to 250M+ speakers worldwide.",
        "pricing_objection": "For less than the cost of a consultant's hour, you get a complete analysis updated monthly.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with pastel de nata and persistence.",
    },
    "NL": {
        "name": "Netherlands",
        "lang": "en",
        "accent": "#FF6600",
        "accent2": "#21468B",
        "flag_colors": ["#AE1C28", "#fff", "#21468B"],
        "image": "https://images.unsplash.com/photo-1534351590666-13e3e96b5017?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Netherlands — Growth consulting for Dutch startups",
        "meta": "AI-powered traction analysis for Dutch startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Dutch startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. Direct, practical, no nonsense. $39/mo.",
        "startups": "Adyen, Booking.com, Mollie, Messagebird, Elastic",
        "ecosystem_name": "Dutch startup ecosystem",
        "ecosystem_desc": "The Netherlands is a startup powerhouse. Amsterdam is one of Europe's top tech hubs, and Dutch founders are known for building globally from day one. Adyen and Booking.com proved that world-changing companies come from here. The Dutch advantage? Being direct about what works.",
        "market_context": "Whether you're targeting the Benelux, expanding across Europe, or building for global markets from Amsterdam — the analysis adapts. The Netherlands' position as a gateway to Europe is your unfair advantage.",
        "pricing_objection": "Cheaper than an hour with a consultant. Complete analysis updated every month.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with stroopwafels and strategy.",
    },
    "SE": {
        "name": "Sweden",
        "lang": "en",
        "accent": "#006AA7",
        "accent2": "#FECC00",
        "flag_colors": ["#006AA7", "#FECC00", "#006AA7"],
        "image": "https://images.unsplash.com/photo-1509356843151-3e7d96241e11?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Sweden — Growth consulting for Swedish startups",
        "meta": "AI-powered traction analysis for Swedish startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Swedish startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. Lagom advice — just right. $39/mo.",
        "startups": "Spotify, Klarna, King, iZettle, Truecaller",
        "ecosystem_name": "Swedish startup ecosystem",
        "ecosystem_desc": "Sweden produces more unicorns per capita than almost anywhere on Earth. Spotify, Klarna, King — Stockholm is a unicorn factory. The Nordics build globally by default. The question isn't if you can build something great — it's which growth channel gets you there fastest.",
        "market_context": "Whether you're targeting the Nordic markets, expanding across Europe, or building for global scale from Stockholm — the analysis adapts. Swedish startups think global from day one, and so does this analysis.",
        "pricing_objection": "Less than a fika per day. Complete analysis updated monthly.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with fika and focus.",
    },
    "IE": {
        "name": "Ireland",
        "lang": "en",
        "accent": "#169B62",
        "accent2": "#FF883E",
        "flag_colors": ["#169B62", "#fff", "#FF883E"],
        "image": "https://images.unsplash.com/photo-1590089415225-401ed6f9db8e?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Ireland — Growth consulting for Irish startups",
        "meta": "AI-powered traction analysis for Irish startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Irish startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No messing, just results. $39/mo.",
        "startups": "Stripe, Intercom, Wayflyer, Workhuman, LetsGetChecked",
        "ecosystem_name": "Irish startup ecosystem",
        "ecosystem_desc": "Ireland is a startup nation. Stripe alone made it the birthplace of the world's most valuable fintech. Dublin is a European tech hub with a direct line to the US market. The advantage? English-speaking, EU access, incredible talent density.",
        "market_context": "Whether you're building for Ireland, the UK, the EU, or targeting the US from Dublin — the analysis adapts. Ireland's unique position as a bridge between the US and Europe is a massive strategic advantage.",
        "pricing_objection": "Less than a round at the pub. Complete analysis updated monthly.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with Guinness and grit.",
    },
    "PL": {
        "name": "Poland",
        "lang": "en",
        "accent": "#DC143C",
        "accent2": "#fff",
        "flag_colors": ["#fff", "#DC143C", "#fff"],
        "image": "https://images.unsplash.com/photo-1519197924294-4ba991a11128?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Poland — Growth consulting for Polish startups",
        "meta": "AI-powered traction analysis for Polish startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Polish startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. Practical, direct, no fluff. $39/mo.",
        "startups": "CD Projekt, Allegro, DocPlanner, Brainly, LiveChat",
        "ecosystem_name": "Polish startup ecosystem",
        "ecosystem_desc": "Poland is Central Europe's biggest tech market and one of the EU's most dynamic startup scenes. Warsaw and Krakow are producing serious companies. World-class engineering talent at competitive costs — the growth playbook is what turns great tech into great businesses.",
        "market_context": "Whether you're building for the Polish market, expanding across CEE, or targeting Western Europe and beyond from Warsaw — the analysis adapts.",
        "pricing_objection": "Less than a consultant's hourly rate. Complete analysis updated monthly.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with pierogi and precision.",
    },
    "IL": {
        "name": "Israel",
        "lang": "en",
        "accent": "#0038b8",
        "accent2": "#fff",
        "flag_colors": ["#0038b8", "#fff", "#0038b8"],
        "image": "https://images.unsplash.com/photo-1544967082-d9d25d867d66?w=1920&q=80&auto=format&fit=crop",
        "title": "mckoutie Israel — Growth consulting for Israeli startups",
        "meta": "AI-powered traction analysis for Israeli startups. 19 growth channels, 90-day plan, real strategy for $39/mo.",
        "tagline": "Growth consulting for Israeli startups",
        "tagline_sub": "AI-powered traction analysis. 19 growth channels ranked for YOUR startup. 90-day plan. No BS, just tachlis. $39/mo.",
        "startups": "Wiz, Monday.com, Fiverr, ironSource, Gong",
        "ecosystem_name": "Israeli startup ecosystem",
        "ecosystem_desc": "The Startup Nation. More startups per capita than anywhere else. More NASDAQ listings than all of Europe combined. Israeli founders build with urgency and ship fast. But even in the most competitive ecosystem on earth, knowing your growth channel is the difference between a press release and a billion-dollar exit.",
        "market_context": "Whether you're targeting the US from Tel Aviv (like most Israeli startups), building for the European market, or going after emerging markets — the analysis adapts. Israel's home market is small, so you're already thinking global.",
        "pricing_objection": "Less than a consultant's hourly rate. Complete analysis updated monthly. Your startup probably spends more on coffee.",
        "cta_text": "Analyze your startup now",
        "scroll_hint": "scroll for more",
        "footer_tagline": "Built with hummus and hustle.",
    },
}


def _build_footer_links(current_code: str) -> str:
    """Build footer navigation with links to all country pages."""
    links = ['<a href="/">English</a>', '<a href="/AR">Argentina</a>']
    for code, data in sorted(COUNTRIES.items(), key=lambda x: x[1]["name"]):
        if code == current_code:
            links.append(f"<strong>{data['name']}</strong>")
        else:
            links.append(f'<a href="/{code}">{data["name"]}</a>')
    return " &middot; ".join(links)


def render_country_page(code: str) -> str:
    """Render a country landing page HTML string."""
    c = COUNTRIES[code]
    accent = c["accent"]
    accent2 = c["accent2"]
    fc = c["flag_colors"]
    footer_links = _build_footer_links(code)

    return f"""<!DOCTYPE html>
<html lang="{c['lang']}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{c['title']}</title>
    <meta name="description" content="{c['meta']}">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
        :root {{
            --bg: #0a0a0a; --bg2: #111; --card: #141414; --border: #222;
            --text: #e0e0e0; --muted: #666; --accent: {accent}; --accent2: {accent2};
            --green: #00ff88; --orange: #ff6b35;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Space Grotesk', -apple-system, sans-serif;
            background: var(--bg); color: var(--text);
            line-height: 1.6; overflow-x: hidden;
        }}
        .mono {{ font-family: 'Space Mono', monospace; }}

        /* Hero */
        .hero {{
            min-height: 90vh; display: flex; align-items: center;
            justify-content: center; text-align: center;
            padding: 4rem 2rem; position: relative; overflow: hidden;
            background: url('{c["image"]}') center center / cover no-repeat;
        }}
        .hero::before {{
            content: ''; position: absolute; inset: 0;
            background: rgba(10,10,10,0.7);
            pointer-events: none;
        }}
        .hero-content-box {{
            position: relative; z-index: 1;
            background: rgba(10,10,10,0.85);
            border: 1px solid rgba({_hex_to_rgb(accent)},0.3);
            border-radius: 12px;
            padding: 3rem 2.5rem;
            max-width: 700px;
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
        }}
        .flag-bar {{
            width: 100%; height: 4px; position: absolute; top: 0; left: 0;
            background: linear-gradient(90deg, {fc[0]} 33%, {fc[1]} 33%, {fc[1]} 66%, {fc[2]} 66%);
            opacity: 0.5;
        }}
        .logo {{ font-size: 3.5rem; font-weight: 700; letter-spacing: -2px; margin-bottom: 0.3rem; }}
        .logo span {{ color: var(--accent); }}
        .tagline-main {{
            font-size: 1.6rem; color: var(--accent2); font-weight: 600;
            margin-bottom: 1rem;
        }}
        .tagline-sub {{
            font-size: 1.1rem; color: var(--muted); max-width: 550px;
            margin: 0 auto 2.5rem;
        }}
        .cta-hero {{
            display: inline-block; background: var(--accent); color: #fff;
            padding: 16px 40px; font-size: 1.1rem; font-weight: 700;
            text-decoration: none; border-radius: 6px; transition: all 0.2s;
            font-family: 'Space Mono', monospace; letter-spacing: 0.5px;
        }}
        .cta-hero:hover {{ opacity: 0.85; transform: translateY(-1px); }}
        .scroll-hint {{
            position: absolute; bottom: 2rem; left: 50%;
            transform: translateX(-50%);
            color: var(--muted); font-size: 0.85rem;
            animation: bounce 2s infinite;
        }}
        @keyframes bounce {{
            0%, 100% {{ transform: translateX(-50%) translateY(0); }}
            50% {{ transform: translateX(-50%) translateY(8px); }}
        }}

        /* Sections */
        section {{ padding: 5rem 2rem; max-width: 900px; margin: 0 auto; }}
        .section-title {{
            font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem;
        }}
        .section-title span {{ color: var(--accent); }}
        .section-sub {{ color: var(--muted); margin-bottom: 2.5rem; font-size: 1.05rem; }}

        /* Problem cards */
        .problema-grid {{
            display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;
        }}
        .problema-card {{
            background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 1.5rem;
        }}
        .problema-card .emoji {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
        .problema-card h3 {{ color: var(--accent); font-size: 1rem; margin-bottom: 0.5rem; }}
        .problema-card p {{ color: var(--muted); font-size: 0.9rem; }}

        /* Steps */
        .steps {{ counter-reset: step; }}
        .step {{
            display: flex; gap: 1.5rem; align-items: flex-start;
            margin-bottom: 2rem;
        }}
        .step-num {{
            flex-shrink: 0; width: 48px; height: 48px;
            background: var(--card); border: 2px solid var(--accent);
            border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-weight: 700; color: var(--accent);
            font-family: 'Space Mono', monospace; font-size: 1.1rem;
        }}
        .step-content h3 {{ font-size: 1.1rem; margin-bottom: 0.3rem; }}
        .step-content p {{ color: var(--muted); font-size: 0.95rem; }}
        .step-content code {{
            background: #1a1a1a; color: var(--accent); padding: 3px 8px;
            border-radius: 4px; font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
        }}

        /* Features */
        .features {{
            display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
        }}
        .feature {{
            background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 1.2rem;
        }}
        .feature .check {{ color: var(--green); margin-right: 0.5rem; font-weight: 700; }}
        .feature h3 {{ font-size: 0.95rem; margin-bottom: 0.3rem; display: flex; align-items: center; }}
        .feature p {{ color: var(--muted); font-size: 0.85rem; padding-left: 1.5rem; }}

        /* Pricing */
        .pricing-grid {{
            display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem;
        }}
        .price-card {{
            background: var(--card); border: 1px solid var(--border);
            border-radius: 10px; padding: 2rem 1.5rem; text-align: center;
            position: relative;
        }}
        .price-card.featured {{
            border-color: var(--accent);
            box-shadow: 0 0 30px rgba({_hex_to_rgb(accent)},0.1);
        }}
        .price-card .badge {{
            position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
            background: var(--accent); color: #fff; padding: 4px 16px;
            border-radius: 20px; font-size: 0.75rem; font-weight: 700;
        }}
        .price-card h3 {{ font-size: 1.2rem; margin-bottom: 0.5rem; }}
        .price-amount {{ font-size: 2.5rem; font-weight: 700; color: var(--accent); }}
        .price-amount span {{ font-size: 1rem; color: var(--muted); }}
        .price-card ul {{
            list-style: none; text-align: left; margin: 1.5rem 0;
            font-size: 0.85rem; color: var(--muted);
        }}
        .price-card ul li {{ padding: 0.4rem 0; border-bottom: 1px solid #1a1a1a; }}
        .price-card ul li::before {{ content: '-> '; color: var(--accent); }}

        /* Context box */
        .context-box {{
            background: var(--card); border-left: 3px solid var(--accent);
            padding: 1.5rem 2rem; border-radius: 0 8px 8px 0;
            margin: 2rem 0;
        }}
        .context-box p {{ color: var(--muted); font-size: 0.95rem; margin: 0.3rem 0; }}
        .context-box strong {{ color: var(--text); }}

        /* Credibility */
        .credibility {{
            text-align: center; padding: 3rem 2rem;
            border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
            margin: 2rem 0;
        }}
        .credibility p {{ color: var(--muted); font-size: 1rem; max-width: 600px; margin: 0.5rem auto; }}
        .credibility .highlight {{ color: var(--accent); font-weight: 600; }}

        /* CTA bottom */
        .cta-section {{ text-align: center; padding: 5rem 2rem; }}
        .cta-section h2 {{ font-size: 2rem; margin-bottom: 1rem; }}
        .cta-section p {{ color: var(--muted); margin-bottom: 2rem; max-width: 500px; margin-left: auto; margin-right: auto; }}
        .cta-bottom {{
            display: inline-block; background: var(--green); color: #0a0a0a;
            padding: 16px 48px; font-size: 1.15rem; font-weight: 700;
            text-decoration: none; border-radius: 6px; transition: all 0.2s;
            font-family: 'Space Mono', monospace;
        }}
        .cta-bottom:hover {{ background: #00cc6a; transform: translateY(-1px); }}

        /* Footer */
        footer {{
            text-align: center; padding: 2rem 1rem; color: #333;
            font-size: 0.8rem; border-top: 1px solid #1a1a1a;
        }}
        footer a {{ color: var(--accent); text-decoration: none; }}
        footer strong {{ color: var(--text); }}
        .footer-links {{ flex-wrap: wrap; display: flex; justify-content: center; gap: 0.3rem; }}

        /* Responsive */
        @media (max-width: 700px) {{
            .hero {{ min-height: auto; padding: 3rem 1.5rem; }}
            .logo {{ font-size: 2.5rem; }}
            .tagline-main {{ font-size: 1.3rem; }}
            .problema-grid, .features, .pricing-grid {{ grid-template-columns: 1fr; }}
            section {{ padding: 3rem 1.5rem; }}
        }}
    </style>
</head>
<body>

<!-- Hero -->
<div class="hero">
    <div class="flag-bar"></div>
    <div class="hero-content-box">
        <div class="logo">mck<span>ou</span>tie</div>
        <p class="tagline-main">{c['tagline']}</p>
        <p class="tagline-sub">{c['tagline_sub']}</p>
        <a class="cta-hero" href="https://x.com/intent/tweet?text=@mckoutie%20analyse%20my%20startup%20" target="_blank">
            {c['cta_text']}
        </a>
    </div>
    <div class="scroll-hint">&#8595; {c['scroll_hint']}</div>
</div>

<!-- The problem -->
<section>
    <h2 class="section-title">The <span>problem</span> we all know</h2>
    <p class="section-sub">Building a startup is hard enough. The consulting industry makes it worse.</p>

    <div class="problema-grid">
        <div class="problema-card">
            <div class="emoji">&#128184;</div>
            <h3>McKinsey charges $100K+</h3>
            <p>And they don't even understand your market. Their playbook was designed for Fortune 500s, not startups.</p>
        </div>
        <div class="problema-card">
            <div class="emoji">&#129335;</div>
            <h3>"Just do content marketing"</h3>
            <p>Generic advice everyone gives. But which specific channel actually moves the needle for YOUR startup?</p>
        </div>
        <div class="problema-card">
            <div class="emoji">&#9200;</div>
            <h3>Time is your scarcest resource</h3>
            <p>You're the CEO, CTO, and community manager. You don't have 3 months for a "market study".</p>
        </div>
        <div class="problema-card">
            <div class="emoji">&#127758;</div>
            <h3>You think global from day 1</h3>
            <p>Your startup isn't just for {c['name']}. You need a strategy that scales beyond borders.</p>
        </div>
    </div>
</section>

<!-- Ecosystem context -->
<section>
    <h2 class="section-title">Built for the <span>{c['ecosystem_name']}</span></h2>
    <p class="section-sub">Not a generic tool. It understands your context.</p>

    <div class="context-box">
        <p><strong>The talent in {c['name']} is world-class.</strong> {c['ecosystem_desc']}</p>
        <p>{c['startups']} — all born here. The difference between the ones that scale and the ones that die isn't the product. It's traction.</p>
    </div>

    <div class="context-box">
        <p><strong>Mckoutie analyzes your startup with the Bullseye framework</strong> — the same one used by the most successful startups in the world to find their primary growth channel.</p>
        <p>19 channels. Each scored 1-10 for your specific case. Not generic — for YOU.</p>
    </div>

    <div class="context-box">
        <p><strong>{c['market_context']}</strong></p>
    </div>
</section>

<!-- How it works -->
<section>
    <h2 class="section-title">How it <span>works</span></h2>
    <p class="section-sub">Three steps. Two minutes. Zero bureaucracy.</p>

    <div class="steps">
        <div class="step">
            <div class="step-num">1</div>
            <div class="step-content">
                <h3>Tweet at @mckoutie</h3>
                <p>Send a tweet: <code>@mckoutie analyse my startup https://yourstartup.com</code></p>
                <p>You can also tag a company: <code>@mckoutie analyse my startup @yourhandle</code></p>
            </div>
        </div>
        <div class="step">
            <div class="step-num">2</div>
            <div class="step-content">
                <h3>Get a free teaser</h3>
                <p>Within minutes, mckoutie replies with a thread showing your top 3 channels and a hot take. Free. No credit card.</p>
            </div>
        </div>
        <div class="step">
            <div class="step-num">3</div>
            <div class="step-content">
                <h3>Unlock the full analysis</h3>
                <p>Subscribe for $39/mo and access the interactive dashboard with all 19 channels, 90-day plan, leads, investors, and monthly updates.</p>
            </div>
        </div>
    </div>
</section>

<!-- What's included -->
<section>
    <h2 class="section-title">What's <span>included</span></h2>
    <p class="section-sub">Everything you need to stop guessing and start growing.</p>

    <div class="features">
        <div class="feature">
            <h3><span class="check">&#10003;</span> 19 channels analyzed</h3>
            <p>From SEO and content to partnerships and engineering as marketing. Each with score and specific tactics.</p>
        </div>
        <div class="feature">
            <h3><span class="check">&#10003;</span> Bullseye framework</h3>
            <p>Your channels ranked in inner ring, middle ring, and outer ring. Know exactly where to bet.</p>
        </div>
        <div class="feature">
            <h3><span class="check">&#10003;</span> 90-day plan</h3>
            <p>Week by week. What to do, how to measure it, what to expect. No vague "define your strategy".</p>
        </div>
        <div class="feature">
            <h3><span class="check">&#10003;</span> Budget allocation</h3>
            <p>How much to put in each channel with whatever budget you have, whether it's $500 or $50,000.</p>
        </div>
        <div class="feature">
            <h3><span class="check">&#10003;</span> Risk matrix</h3>
            <p>Real risks to your model and how to mitigate them. No sugarcoating.</p>
        </div>
        <div class="feature">
            <h3><span class="check">&#10003;</span> Hot take</h3>
            <p>What no one else will tell you. The uncomfortable truth about your startup. Sometimes it hurts, always useful.</p>
        </div>
        <div class="feature">
            <h3><span class="check">&#10003;</span> Leads + personas</h3>
            <p>3 ideal customer personas + 10 real leads to start selling today. (Growth plan)</p>
        </div>
        <div class="feature">
            <h3><span class="check">&#10003;</span> Investor intel</h3>
            <p>Who invested in your competitors, which funds watch your vertical, and how to approach them. (Growth plan)</p>
        </div>
    </div>
</section>

<!-- Pricing -->
<section>
    <h2 class="section-title">Real <span>pricing</span></h2>
    <p class="section-sub">No fine print. No contracts. Cancel anytime.</p>

    <div class="pricing-grid">
        <div class="price-card">
            <h3>Teaser</h3>
            <div class="price-amount">Free</div>
            <ul>
                <li>Top 3 growth channels</li>
                <li>Hot take on your startup</li>
                <li>Public Twitter thread</li>
                <li>No credit card, no signup</li>
            </ul>
        </div>
        <div class="price-card featured">
            <div class="badge">MOST POPULAR</div>
            <h3>Starter</h3>
            <div class="price-amount">$39<span>/mo</span></div>
            <ul>
                <li>19 channels with scores &amp; tactics</li>
                <li>Full Bullseye framework</li>
                <li>Weekly 90-day plan</li>
                <li>Budget allocation</li>
                <li>Risk matrix + moat analysis</li>
                <li>Unfiltered hot take</li>
                <li>Monthly market updates</li>
            </ul>
        </div>
        <div class="price-card">
            <h3>Growth</h3>
            <div class="price-amount">$200<span>/mo</span></div>
            <ul>
                <li>Everything in Starter</li>
                <li>3 detailed customer personas</li>
                <li>10 real leads with contact info</li>
                <li>Investor intelligence</li>
                <li>Competitor funding data</li>
                <li>Monthly market deep dives</li>
            </ul>
        </div>
    </div>

    <div class="context-box" style="margin-top: 2rem;">
        <p><strong>{c['pricing_objection']}</strong></p>
    </div>
</section>

<!-- Credibility -->
<div class="credibility">
    <p class="highlight">Built for founders who think big, wherever they are.</p>
    <p>Based on the "Traction" framework by Gabriel Weinberg (founder of DuckDuckGo). Powered by AI. Designed for startups that don't have time or budget for corporate consulting theater.</p>
    <p style="margin-top: 1rem; font-size: 0.85rem;">The same framework used by Dropbox, HubSpot, and hundreds of YC startups to find their growth channel.</p>
</div>

<!-- Final CTA -->
<div class="cta-section">
    <h2>Ready to stop guessing?</h2>
    <p>In 2 minutes you get a professional traction analysis. The teaser is free. If it's not useful, you pay nothing.</p>
    <a class="cta-bottom" href="https://x.com/intent/tweet?text=@mckoutie%20analyse%20my%20startup%20" target="_blank">
        {c['cta_text']} &#8594;
    </a>
    <p style="color: var(--muted); font-size: 0.85rem; margin-top: 1rem;">
        Tweet at <a href="https://x.com/mckoutie" target="_blank" style="color: var(--accent); text-decoration: none;">@mckoutie</a> and get started.
    </p>
</div>

<!-- Footer -->
<footer>
    <p>mckoutie — McKinsey at home</p>
    <p class="footer-links" style="margin-top: 0.5rem;">
        {footer_links}
        &middot; <a href="https://x.com/mckoutie" target="_blank">Twitter</a>
    </p>
    <p style="margin-top: 1rem;">{c['footer_tagline']}</p>
</footer>

</body>
</html>"""


def _hex_to_rgb(hex_color: str) -> str:
    """Convert hex color to comma-separated RGB values for rgba()."""
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"
