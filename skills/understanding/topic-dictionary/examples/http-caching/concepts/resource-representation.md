---
title: "Resource Representation"
slug: "resource-representation"
section: "Foundations"
section_order: 1
order: 1
summary: "A representation is the transferable form of a resource that an HTTP cache can store and reuse."
prerequisites: []
related:
  - "cache-freshness"
sources:
  - "https://www.rfc-editor.org/rfc/rfc9110.html"
---

# Resource Representation

## What is it?

A resource representation is the bytes and metadata transferred for the current state of an HTTP resource. The resource is the abstract target identified by a URL; the representation is one concrete form, such as JSON or an English-language HTML document.

## Why does it exist?

Clients cannot directly receive an abstract resource. They need a serializable form with enough metadata to interpret it. Separating resource from representation also lets one URL provide different formats, languages, or encodings without pretending they are different underlying resources.

## How does it work?

A client requests a URL and may state which forms it understands. The server selects a representation, sends its bytes, and describes them with response headers such as content type and content encoding. A cache stores that response together with the request properties needed to select it safely later.

## When is it used?

The distinction matters whenever a server performs content negotiation or a cache reuses responses. For example, English and Japanese HTML for one URL are separate representations. It matters less when an endpoint has only one fixed response form and is never cached.

## Common misconceptions

A representation is not the resource itself. Deleting one cached JSON response does not delete the underlying account resource; it removes one stored description of that resource. Likewise, two representations can differ in bytes while describing the same resource state.

## Related concepts

[Cache freshness](cache-freshness.md) determines when a stored representation may be reused without contacting its origin. Cache-Control then communicates rules that govern storage and reuse of that representation.

## What to learn next

Learn [cache freshness](cache-freshness.md) next to see why a stored representation can be reusable at one moment and require validation at another.
