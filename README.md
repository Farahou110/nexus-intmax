# nexus-intmax
Overview: Nexus-Intmax is a web-based community management platform designed to automate the tracking of social engagement for the Intmax ecosystem. It simplifies the onboarding process for community members ("Fellows") and provides real-time analytics on their contributions, ensuring transparent and data-driven community growth.

Key Features:

    Seamless Social Authentication: Implements Twitter OAuth for secure, one-click login and registration, eliminating the need for traditional passwords.

    Automated Data Analytics: Integrates with the Twitter API v2 to automatically fetch and aggregate user performance metrics (Impressions, Likes, and Retweets) without manual input.

    Real-Time Dashboard: Features a dynamic user dashboard (/dashboard) that visualizes individual engagement data, allowing fellows to track their impact.

    Scalable Architecture: Built on MongoDB, a NoSQL database, to handle dynamic user data and scalable engagement logs efficiently.

    Role-Based Access: Includes a flexible user model distinguishing between different community roles for future administrative scalability.

How It Works:

    Authentication: Users log in via their Twitter accounts. The system verifies credentials and ensures they are registered in the system.

    Data Ingestion: Upon login, a background utility (fetch_twitter_metrics) queries the Twitter API to retrieve the user's latest interaction stats.

    Storage & Display: These metrics are processed and stored in the engagements collection in MongoDB, then rendered on the frontend dashboard for the user.
