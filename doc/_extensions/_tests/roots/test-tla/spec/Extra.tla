------------------------------ MODULE Extra ------------------------------
(* Edge cases for the extractor of tla_domain. Not a model. *)
EXTENDS Naturals, Sequences

CONSTANT N, F(_, _)
VARIABLE x

\* An infix operator.
a ++ b == a + b + 1

\* A prefix operator.
-. a == 0 - a

\* A postfix operator.
a ^# == a * a

\* A local definition.
LOCAL Helper(n) == n + 1

\* The sum of a sequence. The doc comment is above RECURSIVE.
RECURSIVE Sum(_)
Sum(s) == IF s = <<>> THEN 0 ELSE Head(s) + Sum(Tail(s))

(***************************************************************************)
(* A box comment as the doc comment.                                       *)
(*                                                                         *)
(* The text can use *RST* markup.                                          *)
(***************************************************************************)
Double[k \in Nat] == 2 * k

(* A block comment
   on two lines. *)
Long(p,
     q) ==
    \* An indented comment is part of the body.
    (* A nested (* block *) comment. *)
    /\ p \in Nat
    /\ q \in Nat

\* An instance.
\* @kind definition
Seqs == INSTANCE Sequences

\* A string with == and \* in it, and a comment with ==.
Text == "a == b \* c"   \* not a definition == here

\* @kind action
\* @c-function k_extra_step
Step == x' = x ++ 1

Init == x = 0
Spec == Init /\ [][Step]_x

THEOREM SpecTyped == Spec => [](x \in Nat)

(* --algorithm Counter
variables y = 0;
begin
  L1: y := y + 1;
end algorithm; *)

=============================================================================
Text after the footer is not part of the module.
Ghost == 1
