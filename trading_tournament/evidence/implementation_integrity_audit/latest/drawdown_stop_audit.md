# Drawdown Stop Audit

Research-sample runners track rolling peak-to-current equity drawdown as a negative dollar value. The current fast wrapper runners flag `absolute_600_stop_hit` when profit from starting equity falls to `-$600`; GROR candidate validation also exports drawdown distributions. The stop and drawdown signs are not inverted in the inspected live code.
