---- MODULE Bad ----
\* @foo bar
\* @kind wrong
\* @expected maybe
Ok == TRUE

Prop == TRUE

\* A helper with the type annotations of Apalache.
\* @typeAlias: pair = <<Int, Int>>;
\* @type: Int => $pair;
Typed(n) == <<n, n>>
====
