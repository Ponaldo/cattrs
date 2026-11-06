from typing import Optional, Sequence, Union

import pytest
from attrs import define

from cattrs import BaseConverter, Converter
from cattrs.strategies import configure_tagged_union


@define
class A:
    a: int


@define
class B:
    a: str


@define
class C:
    a: int


def test_defaults(converter: BaseConverter) -> None:
    """Defaults should work."""
    union = Union[A, B]
    configure_tagged_union(union, converter)

    assert converter.unstructure(A(1), union) == {"_type": "A", "a": 1}
    assert converter.unstructure(B("1"), union) == {"_type": "B", "a": "1"}

    assert converter.structure({"_type": "A", "a": 1}, union) == A(1)
    assert converter.structure({"_type": "B", "a": 1}, union) == B("1")


def test_tag_name(converter: BaseConverter) -> None:
    """Tag names are customizable."""
    union = Union[A, B]
    tag_name = "t"
    configure_tagged_union(union, converter, tag_name=tag_name)

    assert converter.unstructure(A(1), union) == {tag_name: "A", "a": 1}
    assert converter.unstructure(B("1"), union) == {tag_name: "B", "a": "1"}

    assert converter.structure({tag_name: "A", "a": 1}, union) == A(1)
    assert converter.structure({tag_name: "B", "a": 1}, union) == B("1")


def test_tag_generator(converter: BaseConverter) -> None:
    """Tag values are customizable using a callable."""
    union = Union[A, B]
    configure_tagged_union(
        union, converter, tag_generator=lambda t: f"{t.__module__}.{t.__name__}"
    )

    assert converter.unstructure(A(1), union) == {
        "_type": "tests.strategies.test_tagged_unions.A",
        "a": 1,
    }
    assert converter.unstructure(B("1"), union) == {
        "_type": "tests.strategies.test_tagged_unions.B",
        "a": "1",
    }

    assert converter.structure(
        {"_type": "tests.strategies.test_tagged_unions.A", "a": 1}, union
    ) == A(1)
    assert converter.structure(
        {"_type": "tests.strategies.test_tagged_unions.B", "a": 1}, union
    ) == B("1")


def test_tag_generator_dict(converter: BaseConverter) -> None:
    """Tag values are customizable using a dict."""
    union = Union[A, B]
    configure_tagged_union(
        union,
        converter,
        tag_generator={cl: f"type:{cl.__name__}" for cl in union.__args__}.get,
    )

    assert converter.unstructure(A(1), union) == {"_type": "type:A", "a": 1}
    assert converter.unstructure(B("1"), union) == {"_type": "type:B", "a": "1"}

    assert converter.structure({"_type": "type:A", "a": 1}, union) == A(1)
    assert converter.structure({"_type": "type:B", "a": 1}, union) == B("1")


def test_default_member(converter: BaseConverter) -> None:
    """Tagged unions can have default members."""
    union = Union[A, B]
    configure_tagged_union(union, converter, default=A)
    assert converter.unstructure(A(1), union) == {"_type": "A", "a": 1}
    assert converter.unstructure(B("1"), union) == {"_type": "B", "a": "1"}

    # No tag, so should structure as A.
    assert converter.structure({"a": 1}, union) == A(1)
    # Wrong tag, so should again structure as A.
    assert converter.structure({"_type": "C", "a": 1}, union) == A(1)

    assert converter.structure({"_type": "A", "a": 1}, union) == A(1)
    assert converter.structure({"_type": "B", "a": 1}, union) == B("1")


def test_default_member_with_tag(converter: BaseConverter) -> None:
    """Members can access the tags, if not `forbid_extra_keys`."""

    @define
    class C:
        _type: str = ""

    union = Union[A, B, C]
    configure_tagged_union(union, converter, default=C)
    assert converter.unstructure(A(1), union) == {"_type": "A", "a": 1}
    assert converter.unstructure(B("1"), union) == {"_type": "B", "a": "1"}

    # No tag, so should structure as C.
    assert converter.structure({"a": 1}, union) == C()
    # Wrong tag, so should again structure as C.
    assert converter.structure({"_type": "D", "a": 1}, union) == C("D")

    assert converter.structure({"_type": "A", "a": 1}, union) == A(1)
    assert converter.structure({"_type": "B", "a": 1}, union) == B("1")
    assert converter.structure({"_type": "C", "a": 1}, union) == C("C")


def test_default_member_validation(converter: BaseConverter) -> None:
    """Default members are structured properly.."""
    union = Union[A, B]
    configure_tagged_union(union, converter, default=A)

    # A.a should be coerced to an int.
    assert converter.structure({"_type": "A", "a": "1"}, union) == A(1)


def test_forbid_extra_keys():
    """The strategy works when converters forbid extra keys."""

    @define
    class A:
        pass

    @define
    class B:
        pass

    c = Converter(forbid_extra_keys=True)
    configure_tagged_union(Union[A, B], c)

    data = c.unstructure(A(), Union[A, B])
    c.structure(data, Union[A, B])


def test_forbid_extra_keys_default():
    """The strategy works when converters forbid extra keys."""

    @define
    class A:
        pass

    @define
    class B:
        pass

    c = Converter(forbid_extra_keys=True)
    configure_tagged_union(Union[A, B], c, default=A)

    data = c.unstructure(A(), Union[A, B])
    assert c.structure(data, Union[A, B]) == A()

    data.pop("_type")
    assert c.structure(data, Union[A, B]) == A()


def test_nested_sequence_union():
    @define
    class Top:
        u: Optional[Sequence[Union[A, B]]]

    c = Converter()
    configure_tagged_union(Union[A, B], c)

    data = c.unstructure(Top(u=[B(a="")]), Top)
    c.structure(data, Top)


def test_tagged_union_allow_subsets_round_trip(converter: BaseConverter) -> None:
    """Subset unions can opt into the tagged strategy when configured to do so."""

    @define
    class WithSubset:
        value: Union[A, B]

    configure_tagged_union(Union[A, B, C], converter, allow_subsets=True)

    value = WithSubset(value=B("1"))
    data = converter.unstructure(value, WithSubset)

    assert data == {"value": {"_type": "B", "a": "1"}}
    assert converter.structure(data, WithSubset) == value


def test_tagged_union_allow_subsets_rejects_unrelated_tag(
    converter: BaseConverter,
) -> None:
    """Subset unions should reject tags from excluded members."""
    configure_tagged_union(Union[A, B, C], converter, allow_subsets=True)

    with pytest.raises(KeyError):
        converter.structure({"_type": "C", "a": 1}, Union[A, B])


def test_tagged_union_without_allow_subsets_keeps_legacy_behavior(
    converter: BaseConverter,
) -> None:
    """The legacy subset behavior stays unchanged unless allow_subsets is enabled."""

    @define
    class WithSubset:
        value: Union[A, B]

    configure_tagged_union(Union[A, B, C], converter)

    value = WithSubset(value=B("1"))
    assert converter.unstructure(value, WithSubset) == {"value": {"a": "1"}}
    with pytest.raises(TypeError):
        converter.structure({"value": {"a": "1"}}, WithSubset)


def test_tagged_union_subset_uses_included_default(converter: BaseConverter) -> None:
    """A subset can use the configured default when it is a member."""
    configure_tagged_union(Union[A, B, C], converter, default=A, allow_subsets=True)

    assert converter.structure({"a": 1}, Union[A, B]) == A(1)


def test_tagged_union_subset_ignores_excluded_default(converter: BaseConverter) -> None:
    """A default outside the subset is not used when its tag is missing."""
    configure_tagged_union(Union[A, B, C], converter, default=C, allow_subsets=True)

    with pytest.raises(KeyError):
        converter.structure({"a": 1}, Union[A, B])


def test_tagged_union_subset_unknown_tag_uses_included_default(
    converter: BaseConverter,
) -> None:
    """Unknown tags use the default, but tags for excluded classes do not."""
    configure_tagged_union(Union[A, B, C], converter, default=A, allow_subsets=True)
    value = {"_type": "zzz", "a": 1}

    assert converter.structure(value, Union[A, B, C]) == A(1)
    assert converter.structure(value, Union[A, B]) == A(1)
    with pytest.raises(KeyError):
        converter.structure({"_type": "C", "a": 1}, Union[A, B])


def test_tagged_union_subset_forbid_extra_keys() -> None:
    """Subset tags are removed before structuring when extra keys are forbidden."""
    converter = Converter(forbid_extra_keys=True)
    subset = Union[A, B]
    configure_tagged_union(Union[A, B, C], converter, allow_subsets=True)

    data = converter.unstructure(B("1"), subset)
    assert data == {"_type": "B", "a": "1"}
    assert converter.structure(data, subset) == B("1")


def test_tagged_union_reordered_subset(converter: BaseConverter) -> None:
    """Subsets use the tagged strategy regardless of member order."""
    subset = Union[B, A]
    configure_tagged_union(Union[A, B, C], converter, allow_subsets=True)

    data = converter.unstructure(A(1), subset)
    assert data == {"_type": "A", "a": 1}
    assert converter.structure(data, subset) == A(1)


def test_tagged_union_subset_preserves_registered_hooks(
    converter: BaseConverter,
) -> None:
    """Previously registered hooks for a subset take precedence."""
    subset = Union[A, B]
    converter.register_structure_hook(subset, lambda _, __: A(2))
    converter.register_unstructure_hook(subset, lambda _: {"custom": True})
    configure_tagged_union(Union[A, B, C], converter, allow_subsets=True)

    assert converter.structure({}, subset) == A(2)
    assert converter.unstructure(A(1), subset) == {"custom": True}
