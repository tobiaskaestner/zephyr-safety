Resume a campaign
=================

``resume`` runs the experiments of a campaign that are not ``done`` or
``skipped``, also the ``failed`` ones: at the start it sets them to
``planned`` again (``attempts`` + 1), so they make the verdicts
provisional until they run. The design repository must be at
the commit of the campaign. To get it, check out the ref
``refs/latbench/campaign/<id>``.
