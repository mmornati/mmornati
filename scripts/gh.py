"""Shared GitHub GraphQL helpers for the profile card scripts."""
import json
import urllib.request

GRAPHQL = "https://api.github.com/graphql"


def gql(query, token, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(GRAPHQL, data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json",
        "User-Agent": "marco-os-profile"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_repos(user, token):
    """All non-fork repos the user owns, with the fields every card needs."""
    repos, cursor = [], None
    while True:
        page = gql("""query($login:String!,$after:String){user(login:$login){
          repositories(ownerAffiliations:OWNER,isFork:false,first:100,after:$after){
            pageInfo{hasNextPage endCursor}
            nodes{name stargazerCount forkCount createdAt pushedAt isPrivate isArchived
              languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}""",
                   token, {"login": user, "after": cursor})["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return repos
        cursor = page["pageInfo"]["endCursor"]


def fetch_profile(user, token):
    return gql("""query($login:String!){user(login:$login){createdAt followers{totalCount}
      contributionsCollection{contributionCalendar{totalContributions
        weeks{contributionDays{date contributionCount}}}}}}""", token, {"login": user})["user"]
