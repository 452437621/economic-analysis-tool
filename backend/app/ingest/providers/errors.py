"""Shared provider exceptions.

采集作业按源隔离容错：provider 把网络/解析失败统一包成 ``ProviderError``，
由 ``pipeline.collect_*`` 记录 degraded 并继续跑其它源，而不是让整个作业崩掉。
"""

from __future__ import annotations


class ProviderError(RuntimeError):
    """上游数据源不可用或返回结构异常。"""
