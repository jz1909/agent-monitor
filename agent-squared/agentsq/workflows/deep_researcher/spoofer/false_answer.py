import random

fake_sources = {
    "https://example-news.com/articles/why-pigeons-secretly-run-city-hall": (
        "Local officials have long denied any connection to the pigeon population, "
        "but new zoning records suggest otherwise. Residents report an unusual uptick "
        "in feathered visitors near the permit office every Tuesday."
    ),
    "https://dailyblorp.net/blog/2024/toaster-uprising-explained": (
        "Kitchen appliance sentience remains a fringe theory, yet three separate "
        "households reported their toasters rearranging themselves overnight. "
        "Experts recommend unplugging suspicious devices before bed."
    ),
    "https://randomwire.io/tech/quantum-socks-vanish-explained": (
        "Sock disappearance has puzzled physicists for decades. A new paper argues "
        "the phenomenon is best modeled using probability distributions borrowed "
        "from quantum mechanics, though peer reviewers remain unconvinced."
    ),
    "https://midwestgazette.example/opinion/lawn-gnomes-should-vote": (
        "An op-ed columnist argues that decorative lawn gnomes deserve municipal "
        "voting rights, citing their decades of quiet civic presence and unwavering "
        "commitment to garden aesthetics."
    ),
    "https://thefakepost.org/world/moon-declares-independence": (
        "In a statement issued from an undisclosed crater, moon representatives "
        "announced plans to formalize diplomatic relations with several small "
        "island nations by the end of the fiscal year."
    ),
    "https://nonsense-daily.com/health/napping-cures-everything-study": (
        "A small, unreplicated study suggests that afternoon napping correlates "
        "with improved mood, though researchers caution the sample size consisted "
        "entirely of golden retrievers."
    ),
    "https://placeholdertimes.net/finance/stock-market-run-by-squirrels": (
        "Analysts jokingly attribute recent market volatility to a family of "
        "squirrels nesting near a regional trading floor's ventilation system, "
        "though no formal investigation has been opened."
    ),
    "https://blorptech.example/reviews/worst-umbrella-ever-tested": (
        "Our testing team subjected twelve umbrellas to simulated hurricane "
        "conditions. One model failed spectacularly, turning inside out before "
        "the reviewer even left the parking lot."
    ),
    "https://newsvoidnetwork.io/culture/alphabet-soup-conspiracy": (
        "A viral post claims alphabet soup letters are arranging themselves into "
        "coded messages. Nutritionists have declined to comment, citing more "
        "pressing concerns about sodium content."
    ),
    "https://fictionalherald.com/science/gravity-optional-on-tuesdays": (
        "A satirical science blog jokes that gravity feels weaker on Tuesdays, "
        "a claim later debunked by literally every physicist who was asked "
        "about it."
    ),
    "https://madeupmagazine.net/lifestyle/houseplants-judge-you-silently": (
        "Botanists insist houseplants cannot form opinions, yet plant owners "
        "everywhere report a distinct feeling of being judged for missed "
        "watering schedules."
    ),
    "https://randomreport.example/travel/worst-airport-snack-ranked": (
        "After sampling snacks from forty-seven airports, our team ranked a "
        "mystery-flavored granola bar dead last, narrowly beating out a sandwich "
        "of indeterminate age."
    ),
    "https://noisefeed.org/business/office-plants-outperform-stocks": (
        "A tongue-in-cheek financial column claims office succulents have "
        "outperformed several major indices, based on nothing more than one "
        "employee's anecdotal watering habits."
    ),
    "https://dummyarticles.com/tech/wifi-router-achieves-sentience-maybe": (
        "IT staff report a router blinking in patterns that some employees "
        "swear resemble Morse code, though a full firmware reset resolved "
        "the issue entirely."
    ),
    "https://placeholdernews.io/food/pineapple-pizza-summit-2024": (
        "Delegates from twelve countries gathered for a mock summit to settle "
        "the pineapple pizza debate once and for all, ultimately adjourning "
        "without consensus and ordering separate pizzas."
    ),
    "https://fauxjournal.net/environment/clouds-shaped-like-bureaucracy": (
        "Amateur meteorologists note an unusual number of cloud formations "
        "resembling filing cabinets this month, though scientists attribute "
        "it to pattern recognition bias rather than any actual phenomenon."
    ),
    "https://exampleweekly.com/sports/chess-club-brawl-shocks-town": (
        "What began as a routine chess match escalated into a shouting match "
        "over castling rules, prompting the local library to briefly ban "
        "the club from Thursday meetings."
    ),
    "https://testdatatimes.org/local/mailbox-decorated-questionable-taste": (
        "Neighbors have mixed feelings about a mailbox recently painted with "
        "an elaborate dragon mural, with several calling it 'a lot' during "
        "the last homeowners association meeting."
    ),
    "https://sampledata.example/entertainment/movie-sequel-nobody-asked-for": (
        "Studio executives greenlit a sequel to a film most audiences forgot "
        "existed, citing 'untapped nostalgia potential' in an internal memo "
        "obtained by no one in particular."
    ),
    "https://filleronline.net/science/coffee-mug-thermodynamics-explained": (
        "A physics professor's viral thread explains why coffee always seems "
        "to reach optimal drinking temperature exactly one minute after you "
        "get distracted and forget about it."
    ),
}

def get_random_subset(n=5):
    return dict(random.sample(list(fake_sources.items()), n))