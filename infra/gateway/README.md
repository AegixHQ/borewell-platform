# Gateway

Single entry point for all 3 frontend apps. Routes requests to the correct
service and validates JWTs issued by platform-spine before forwarding.
See RFC 0001 §5 for the reasoning.
