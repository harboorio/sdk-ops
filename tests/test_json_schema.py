import pytest
import ast
import black
from sdkops import json_schema


def test_simple_schemas():
    schema1 = {
        "type": "string",
    }
    ast1 = json_schema.to_ast("simple_item", schema1)
    assert (
        black.format_str(ast.unparse(ast1), mode=black.FileMode())
        == """\
simple_item: str
"""
    )

    schema2 = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "year": {"type": "integer"}},
    }
    ast2 = json_schema.to_ast("item_object", schema2)
    assert (
        black.format_str(ast.unparse(ast2), mode=black.FileMode())
        == """\
class ItemObject(dict):

    def __init__(self, name: str = "", year: int = 0):
        super().__init__(name=name, year=year)
        self.name: str = name
        self.year: int = year
"""
    )

    schema3 = {"type": "array", "items": {"type": "string"}}
    ast3 = json_schema.to_ast("item", schema3)
    assert (
        black.format_str(ast.unparse(ast3), mode=black.FileMode())
        == """\
item: list[str]
"""
    )

    schema4 = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "year": {"type": "integer"},
            "items": {"type": "array", "items": {"type": "string"}},
        },
    }
    ast4 = json_schema.to_ast("item_object", schema4)
    assert (
        black.format_str(ast.unparse(ast4), mode=black.FileMode())
        == """\
class ItemObject(dict):

    def __init__(self, name: str = "", year: int = 0, items: list[str] = []):
        super().__init__(name=name, year=year, items=items)
        self.name: str = name
        self.year: int = year
        self.items: list[str] = items
"""
    )

    schema5 = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    ast5 = json_schema.to_ast("item", schema5)
    assert (
        black.format_str(ast.unparse(ast5), mode=black.FileMode())
        == """\
item: str | None
"""
    )

    schema6 = {
        "type": "object",
        "properties": {
            "name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "year": {"type": "integer"},
        },
    }
    ast6 = json_schema.to_ast("my_item", schema6)
    assert (
        black.format_str(ast.unparse(ast6), mode=black.FileMode())
        == """\
class MyItem(dict):

    def __init__(self, name: str | None = None, year: int = 0):
        super().__init__(name=name, year=year)
        self.name: str | None = name
        self.year: int = year
"""
    )


def test_complex_schemas():
    schema1 = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "price": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                    },
                    "currency": {"type": "string"},
                    "history": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "timestamp": {"type": "string"},
                                "amount": {"type": "integer"},
                            },
                            "required": ["id", "timestamp", "amount"],
                        },
                    },
                },
                "required": ["amount", "currency", "history"],
            },
            "year": {"type": "integer"},
        },
        "required": ["name", "price", "year"],
    }
    ast1 = json_schema.to_ast("complex_item", schema1)
    assert (
        black.format_str(ast.unparse(ast1), mode=black.FileMode(line_length=120))
        == """\
class ComplexItemPriceHistory(dict):

    def __init__(self, amount: int, timestamp: str, id: int):
        super().__init__(id=id, timestamp=timestamp, amount=amount)
        self.id: int = id
        self.timestamp: str = timestamp
        self.amount: int = amount


class ComplexItemPrice(dict):

    def __init__(self, history: list[ComplexItemPriceHistory], currency: str, amount: int):
        super().__init__(amount=amount, currency=currency, history=history)
        self.amount: int = amount
        self.currency: str = currency
        self.history: list[ComplexItemPriceHistory] = history


class ComplexItem(dict):

    def __init__(self, year: int, price: ComplexItemPrice, name: str):
        super().__init__(name=name, price=price, year=year)
        self.name: str = name
        self.price: ComplexItemPrice = price
        self.year: int = year
"""
    )

    schema2 = {
        "type": "object",
        "properties": {
            "response": {
                "anyOf": [
                    {"type": "string"},
                    {
                        "type": "object",
                        "properties": {
                            "status": {"type": "integer"},
                            "message": {"type": "string"},
                        },
                    },
                    {"type": "object", "properties": {"success": {"type": "boolean"}}},
                ]
            },
            "errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                    },
                },
            },
        },
    }
    ast2 = json_schema.to_ast("complex_item", schema2)
    assert (
        black.format_str(ast.unparse(ast2), mode=black.FileMode(line_length=160))
        == """\
class ComplexItemResponse(dict):

    def __init__(self, status: int = 0, message: str = ""):
        super().__init__(status=status, message=message)
        self.status: int = status
        self.message: str = message


class ComplexItemResponse2(dict):

    def __init__(self, success: bool = False):
        super().__init__(success=success)
        self.success: bool = success


class ComplexItemErrors(dict):

    def __init__(self, code: str = "", message: str = ""):
        super().__init__(code=code, message=message)
        self.code: str = code
        self.message: str = message


class ComplexItem(dict):

    def __init__(self, response: str | ComplexItemResponse | ComplexItemResponse2 = "", errors: list[ComplexItemErrors] = []):
        super().__init__(response=response, errors=errors)
        self.response: str | ComplexItemResponse | ComplexItemResponse2 = response
        self.errors: list[ComplexItemErrors] = errors
"""
    )


def test_schema_generate_name_by_ref():
    schema1 = {
        "type": "object",
        "properties": {
            "customer": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "billing_address": {
                        "type": "object",
                        "properties": {
                            "country": {"type": "string"},
                            "city": {"type": "string"},
                        },
                    },
                    "shipping_address": {
                        "$ref": "#/properties/customer/properties/billing_address"
                    },
                },
            },
            "order": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "customer": {"$ref": "#/properties/customer"},
                    "timestamp": {"type": "string"},
                },
            },
        },
    }
    name1 = json_schema.schema_generate_name_by_ref(
        schema1, "#/properties/customer/properties/billing_address"
    )
    assert name1 == "customer_billing_address"

    schema2 = {
        "definitions": {
            "address": {
                "type": "object",
                "properties": {
                    "country": {"type": "string"},
                    "city": {"type": "string"},
                },
            },
        },
    }
    name2 = json_schema.schema_generate_name_by_ref(schema2, "#/definitions/address")
    assert name2 == "address"


def test_ref_resolving():
    schema1 = {
        "type": "object",
        "properties": {
            "customer": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "billing_address": {
                        "type": "object",
                        "properties": {
                            "country": {"type": "string"},
                            "city": {"type": "string"},
                        },
                        "required": ["country", "city"],
                    },
                    "shipping_address": {
                        "$ref": "#/properties/customer/properties/billing_address"
                    },
                },
                "required": ["name", "billing_address", "shipping_address"],
            },
            "order": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "customer": {"$ref": "#/properties/customer"},
                    "timestamp": {"type": "string"},
                },
                "required": ["id", "customer", "timestamp"],
            },
        },
        "required": ["customer", "order"],
    }
    ast1 = json_schema.to_ast("item_with_ref", schema1)
    assert (
        black.format_str(ast.unparse(ast1), mode=black.FileMode(line_length=160))
        == """\
class ItemWithRefCustomerBillingAddress(dict):

    def __init__(self, city: str, country: str):
        super().__init__(country=country, city=city)
        self.country: str = country
        self.city: str = city


class ItemWithRefCustomer(dict):

    def __init__(self, shipping_address: ItemWithRefCustomerBillingAddress, billing_address: ItemWithRefCustomerBillingAddress, name: str):
        super().__init__(name=name, billing_address=billing_address, shipping_address=shipping_address)
        self.name: str = name
        self.billing_address: ItemWithRefCustomerBillingAddress = billing_address
        self.shipping_address: ItemWithRefCustomerBillingAddress = shipping_address


class ItemWithRefOrder(dict):

    def __init__(self, timestamp: str, customer: ItemWithRefCustomer, id: int):
        super().__init__(id=id, customer=customer, timestamp=timestamp)
        self.id: int = id
        self.customer: ItemWithRefCustomer = customer
        self.timestamp: str = timestamp


class ItemWithRef(dict):

    def __init__(self, order: ItemWithRefOrder, customer: ItemWithRefCustomer):
        super().__init__(customer=customer, order=order)
        self.customer: ItemWithRefCustomer = customer
        self.order: ItemWithRefOrder = order
"""
    )

    schema2 = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "customer": {"$ref": "#/components/schemas/customer"},
        },
        "required": ["version", "customer"],
        "components": {
            "schemas": {
                "customer": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                    },
                }
            }
        },
    }
    ast2 = json_schema.to_ast("ref", schema2)
    assert (
        black.format_str(ast.unparse(ast2), mode=black.FileMode(line_length=160))
        == """\
class RefCustomer(dict):

    def __init__(self, id: int = 0):
        super().__init__(id=id)
        self.id: int = id


class Ref(dict):

    def __init__(self, customer: RefCustomer, version: str):
        super().__init__(version=version, customer=customer)
        self.version: str = version
        self.customer: RefCustomer = customer
"""
    )

    schema3 = {
        "type": "object",
        "properties": {
            "customer": {"$ref": "#/components/schemas/CustomerInfo"},
            "order": {"$ref": "#/components/schemas/OrderInfo"},
        },
        "required": ["customer", "order"],
        "components": {
            "schemas": {
                "CustomerInfo": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                    },
                    "required": ["id"],
                },
                "OrderInfo": {
                    "type": "object",
                    "properties": {
                        "no": {"type": "string"},
                    },
                    "required": ["no"],
                },
            }
        },
    }
    ast3 = json_schema.to_ast("ref", schema3)
    assert (
        black.format_str(ast.unparse(ast3), mode=black.FileMode(line_length=160))
        == """\
class RefCustomerInfo(dict):

    def __init__(self, id: int):
        super().__init__(id=id)
        self.id: int = id


class RefOrderInfo(dict):

    def __init__(self, no: str):
        super().__init__(no=no)
        self.no: str = no


class Ref(dict):

    def __init__(self, order: RefOrderInfo, customer: RefCustomerInfo):
        super().__init__(customer=customer, order=order)
        self.customer: RefCustomerInfo = customer
        self.order: RefOrderInfo = order
"""
    )

    schema4 = {
        "type": "object",
        "properties": {
            "point": {
                "anyOf": [
                    {"$ref": "#/components/schemas/MapPoint"},
                    {"type": "null"},
                    {"$ref": "#/components/schemas/IntPoint"},
                ]
            }
        },
        "components": {
            "schemas": {
                "MapPoint": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                    },
                },
                "IntPoint": {"type": "integer"},
            }
        },
    }
    ast4 = json_schema.to_ast("me", schema4)
    assert (
        black.format_str(ast.unparse(ast4), mode=black.FileMode(line_length=160))
        == """\
class MePoint(dict):

    def __init__(self, id: int = 0):
        super().__init__(id=id)
        self.id: int = id


class Me(dict):

    def __init__(self, point: MePoint | None | int = None):
        super().__init__(point=point)
        self.point: MePoint | None | int = point
"""
    )
