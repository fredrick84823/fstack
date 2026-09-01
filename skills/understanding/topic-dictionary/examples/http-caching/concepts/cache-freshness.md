---
title: "Cache Freshness"
slug: "cache-freshness"
section: "Caching Mechanics"
section_order: 2
order: 1
summary: "Freshness determines whether a stored response may satisfy a request without contacting the origin server."
prerequisites:
  - "resource-representation"
related:
  - "cache-control"
sources:
  - "https://www.rfc-editor.org/rfc/rfc9111.html"
---

# Cache Freshness

## What is it?

Cache freshness is the time-dependent status that says a stored [resource representation](resource-representation.md) may be reused without first checking with its origin server. A fresh response is reusable under the request's rules; a stale response normally needs validation or replacement.

## Why does it exist?

Reusing every stored response forever would serve obsolete information, while contacting the origin for every request would eliminate much of caching's speed and load benefit. Freshness creates a bounded period in which reuse is considered safe enough under declared policy.

## How does it work?

The cache calculates how old the stored response is and compares that age with its freshness lifetime. Response headers can set the lifetime explicitly, while caches may estimate it when permitted. If age remains below the lifetime and request rules allow reuse, the cache serves the stored response directly.

## When is it used?

Freshness is evaluated whenever a cache has a candidate response for an incoming request. A versioned image can remain fresh for months, while an account balance may require immediate validation. It should not be treated as proof that the underlying resource has not changed.

## Common misconceptions

Fresh does not mean objectively current. It means the response is still inside an allowed reuse window. A resource can change one second after a long lifetime begins, yet its stored representation remains fresh according to the policy until that lifetime ends.

## Related concepts

[Cache-Control](cache-control.md) carries directives that set freshness lifetimes and alter how stale responses may be handled. A resource representation is the actual stored response whose freshness is evaluated.

## What to learn next

Learn [Cache-Control](cache-control.md) next to understand how servers and clients express the policies used in the freshness calculation.
