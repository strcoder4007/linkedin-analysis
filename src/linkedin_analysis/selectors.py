"""Centralized CSS/XPath selectors for LinkedIn recent activity posts.

Selectors are intentionally conservative and include fallbacks as LinkedIn's
DOM changes frequently. Keep them narrow and scoped to a post container.
"""

# Post container (article preferred, fallback to activity div)
POST_CONTAINER = "article, div[data-urn^='urn:li:activity:']"

# Three-dots menu trigger within a post
MENU_TRIGGER = (
    "button.feed-shared-control-menu__trigger, "
    "button.artdeco-dropdown__trigger[aria-label*='More']"
)
MENU_TRIGGER = "".join(MENU_TRIGGER)  # single CSS selector string

# Menu item label for copying a link
MENUITEM_COPY_LINK_ROLE_NAME = "Copy link to post"

# Content within a post
POST_CONTENT_PRIMARY = "div.update-components-text"
POST_CONTENT_FALLBACK = "div.update-components-update-v2__commentary"

# Timestamp within a post
POST_TIME_EL_PRIMARY = "time[datetime]"
POST_TIME_CONTAINER_FALLBACK = (
    "span.update-components-actor__sub-description.text-body-xsmall"
)
