"""Repositories: the only modules that build SQL (as SQLAlchemy expressions with bound params).

They never commit; the calling service owns the transaction.
"""
