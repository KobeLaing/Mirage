"""Pydantic request/response models.

Response models are allow-lists: only the fields declared here ever leave the
API. Post.ground_truth is deliberately absent from every one of them (SR-17).
"""
