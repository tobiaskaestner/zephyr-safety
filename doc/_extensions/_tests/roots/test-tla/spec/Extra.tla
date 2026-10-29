------------------------------ MODULE Extra ------------------------------
(* Edge cases for the extractor of tla_domain. Not a model. *)
EXTENDS Naturals, Sequences

CONSTANT N, F(_, _)

\* A Kconfig option of kind 2: a constant that changes the behavior.
\* @kconfig CONFIG_EXTRA_SWITCH
CONSTANT Switch

\* The switch is a bool. An assumption with its location.
\* @assumption arch/x/include/x.h:12 (a key_ is 0 if unlocked)
ASSUME Switch \in BOOLEAN

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

\* A step that only the switch enables.
\* @kind action
\* @kconfig CONFIG_EXTRA_SWITCH
\* @assumption doc:x (a step is atomic)
SwitchStep == Switch /\ x' = x

\* Each step increments x. A rule without @expresses: its kind makes the
\* need.
\* @kind action-property
StepIncrements == [][x' = x ++ 1]_x

\* x stays a natural number. A property with @source tags only: the
\* source makes the need, and the requirement UID of the source is a link.
\* @source TEST-REQ-1
\* @source doc:api#x
XIsNat == x \in Nat

\* x stays at most N if the switch is on. A guarded property: its Kconfig
\* options are a field of the need.
\* @kind invariant
\* @kconfig CONFIG_EXTRA_SWITCH, CONFIG_EXTRA_OTHER
\* @assumption doc:x (the option is a bool)
XAtMostN == Switch => x <= N

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
