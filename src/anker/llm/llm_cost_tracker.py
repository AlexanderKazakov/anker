import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from rich.console import Console
from rich.table import Table
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..logging import get_logger

logger = get_logger(__name__)

# Cache file location
CACHE_DIR = Path.home() / ".cache" / "anker"
PRICING_CACHE_FILE = CACHE_DIR / "llm_pricing.json"
PRICING_CACHE_DURATION = timedelta(hours=24)

# Pricing data URL
PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"


def _ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _is_cache_valid() -> bool:
    """Check if cached pricing data is still valid."""
    if not PRICING_CACHE_FILE.exists():
        return False

    cache_age = datetime.now() - datetime.fromtimestamp(PRICING_CACHE_FILE.stat().st_mtime)
    return cache_age < PRICING_CACHE_DURATION


def _load_cached_pricing() -> dict[str, Any] | None:
    """Load pricing data from cache if valid."""
    if not _is_cache_valid():
        return None

    try:
        with open(PRICING_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Loaded pricing data from cache %s", PRICING_CACHE_FILE)
        return data
    except Exception as e:
        logger.warning("Failed to load cached pricing data: %s", e)
        return None


def _save_pricing_to_cache(pricing_data: dict[str, Any]) -> None:
    """Save pricing data to cache."""
    try:
        _ensure_cache_dir()
        with open(PRICING_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(pricing_data, f, indent=2)
        logger.debug("Saved pricing data to cache %s", PRICING_CACHE_FILE)
    except Exception as e:
        logger.warning("Failed to save pricing data to cache: %s", e)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
    retry=retry_if_exception_type((URLError, HTTPError)),
)
def _fetch_pricing_from_url() -> dict[str, Any]:
    """Fetch pricing data from remote URL."""
    logger.info("Fetching model pricing data from %s", PRICING_URL)
    with urlopen(PRICING_URL, timeout=30.0) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data


def get_pricing_data() -> dict[str, Any]:
    """
    Get pricing data, using cache if available and valid.

    Returns cached data if it's less than 24 hours old,
    otherwise fetches fresh data from the remote URL.
    """
    # Try to load from cache first
    cached_data = _load_cached_pricing()
    if cached_data is not None:
        return cached_data

    # Fetch fresh data
    pricing_data = _fetch_pricing_from_url()
    _save_pricing_to_cache(pricing_data)
    return pricing_data


def calculate_llm_cost(usage: dict) -> None:
    """
    Calculate and log the cost breakdown for an API call
    """
    pricing_data = get_pricing_data()
    model = usage["model"]
    if model not in pricing_data:
        logger.warning("Model %s not found in pricing data, unable to calculate costs", model)
        cached_input_price = 0
        uncached_input_price = 0
        output_price = 0
        reasoning_price = 0
    else:
        pricing = pricing_data[model]
        cached_input_price = pricing["cache_read_input_token_cost"]
        uncached_input_price = pricing["input_cost_per_token"]
        output_price = pricing["output_cost_per_token"]
        reasoning_price = output_price

    usage = usage["usage"]
    cached_input_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
    uncached_input_tokens = usage["prompt_tokens"] - cached_input_tokens
    reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
    output_tokens = usage["completion_tokens"] - reasoning_tokens
    total_tokens = usage["total_tokens"]
    if (cached_input_tokens + uncached_input_tokens + reasoning_tokens + output_tokens) != total_tokens:
        logger.warning("Discrepancy in the tokens counts, the usage cost information is not reliable")

    cached_input_cost = cached_input_tokens * cached_input_price
    uncached_input_cost = uncached_input_tokens * uncached_input_price
    reasoning_cost = reasoning_tokens * reasoning_price
    output_cost = output_tokens * output_price
    total_cost = cached_input_cost + uncached_input_cost + reasoning_cost + output_cost
    logger.info("Total LLM API call cost: $%.6f", total_cost)

    # Create and display rich table
    console = Console()
    table = Table(
        title=f"[bold cyan]LLM API Usage Breakdown[/bold cyan]\n[dim]Model: {model}[/dim]", 
        title_justify="center",
        show_header=True,
        header_style="bold magenta",
        border_style="blue",
        show_lines=True
    )
    
    table.add_column("Token Type", style="cyan", justify="left", min_width=20)
    table.add_column("Count", style="green", justify="right", min_width=12)
    table.add_column("Price per 1M", style="yellow", justify="right", min_width=15)
    table.add_column("Cost ($)", style="bright_green", justify="right", min_width=12)
    
    # Add rows for each token type
    table.add_row(
        "Cached Input",
        f"{cached_input_tokens:,}",
        f"${cached_input_price * 1_000_000:,.2f}",
        f"${cached_input_cost:.4f}"
    )
    
    table.add_row(
        "Uncached Input",
        f"{uncached_input_tokens:,}",
        f"${uncached_input_price * 1_000_000:,.2f}",
        f"${uncached_input_cost:.4f}"
    )
    
    table.add_row(
        "Reasoning",
        f"{reasoning_tokens:,}",
        f"${reasoning_price * 1_000_000:,.2f}",
        f"${reasoning_cost:.4f}"
    )
    
    table.add_row(
        "Output",
        f"{output_tokens:,}",
        f"${output_price * 1_000_000:,.2f}",
        f"${output_cost:.4f}"
    )
    
    # Add separator and total row
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_tokens:,}[/bold]",
        "[dim]—[/dim]",
        f"[bold]${total_cost:.4f}[/bold]"
    )
    
    console.print(table)
    console.print()
    
