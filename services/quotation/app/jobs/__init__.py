"""
Real synchronous cross-service call to platform-spine (RFC 0001 section 4
explicitly allows this - services must not touch each other's databases
directly, but calling another service's API is fine).

Closes F-01: a quotation cannot be created without first proving the job
actually exists and recording who its real customer is, so every later
read/approve/reject can check real ownership instead of trusting whatever
ID was supplied by the caller.
"""
