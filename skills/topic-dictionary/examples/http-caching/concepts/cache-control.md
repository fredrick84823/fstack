---
title: "Cache-Control"
slug: "cache-control"
section: "Caching Mechanics"
section_order: 2
order: 2
summary: "Cache-Control carries directives that constrain where an HTTP response is stored and how it is reused."
prerequisites:
  - "resource-representation"
  - "cache-freshness"
related:
  - "cache-freshness"
sources:
  - "https://www.rfc-editor.org/rfc/rfc9111.html"
---

# Cache-Control

## What is it?

Cache-Control is an HTTP header field containing directives for caches and request participants. Its directives govern whether a [resource representation](resource-representation.md) may be stored, how long it remains fresh, where it may be reused, and what must happen before reuse.

## Why does it exist?

Different responses have different privacy, correctness, and performance needs. A public logo can be reused broadly, whereas personalized data may need private storage or mandatory validation. Cache-Control gives senders a standard way to communicate those constraints to independent cache implementations.

## How does it work?

Servers attach response directives such as `max-age`, `private`, or `no-store`; clients can send request directives that further constrain reuse. A cache parses the applicable directives, combines them with response age and request conditions, then stores, serves, validates, or discards the response accordingly.

## When is it used?

Use Cache-Control whenever an HTTP response needs an explicit caching policy. A fingerprinted static asset commonly receives a long lifetime, while sensitive data may prohibit storage. It is not a substitute for changing application state or deleting copies that have already escaped cache control.

## Common misconceptions

`no-cache` does not mean "never store." It normally permits storage but requires validation before reuse. `no-store` is the directive that asks caches not to store the response, although it still cannot revoke copies created before that directive was received.

## Related concepts

[Cache freshness](cache-freshness.md) is the status computed from response age and freshness policy. Resource representation is the response form to which Cache-Control metadata and cache decisions apply.

## What to learn next

The core path is complete. Continue with conditional requests and validators to learn how caches efficiently check whether stale responses can become reusable again.
