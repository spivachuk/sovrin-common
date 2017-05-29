from copy import deepcopy
from hashlib import sha256

from plenum.common.messages.message_base import MessageValidator, MessageBase
from plenum.common.request import Request as PRequest
from plenum.common.constants import TXN_TYPE, RAW, ENC, HASH
from plenum.common.types import OPERATION, \
    ClientMessageValidator as PClientMessageValidator, \
    ClientOperationField as PClientOperationField, TaggedTuples, \
    ConstantField, IdentifierField, NonEmptyStringField, \
    JsonField, NonNegativeNumberField, MapField, LedgerIdField as PLedgerIdField

from sovrin_common.constants import *


class Request(PRequest):
    @property
    def signingState(self):
        """
        Special signing state where the the data for an attribute is hashed
        before signing
        :return: state to be used when signing
        """
        if self.operation.get(TXN_TYPE) == ATTRIB:
            d = deepcopy(super().signingState)
            op = d[OPERATION]
            keyName = {RAW, ENC, HASH}.intersection(set(op.keys())).pop()
            op[keyName] = sha256(op[keyName].encode()).hexdigest()
            return d
        return super().signingState


class ClientGetNymOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(GET_NYM)),
        (TARGET_NYM, IdentifierField()),
    )


class ClientGetTxnsOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(GET_TXNS)),
    )


class ClientDiscloOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(DISCLO)),
        (DATA, NonEmptyStringField()),
        (NONCE, NonEmptyStringField()),
        (TARGET_NYM, IdentifierField(optional=True)),
    )


class ClientSchemaOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(SCHEMA)),
        (DATA, NonEmptyStringField()),
    )


class SchemaField(MessageValidator):

    schema = (
        (NAME, NonEmptyStringField()),
        (VERSION, NonEmptyStringField()),
        (ORIGIN, NonEmptyStringField(optional=True)),
    )


class ClientGetSchemaOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(GET_SCHEMA)),
        (TARGET_NYM, IdentifierField()),
        (DATA, SchemaField()),
    )


class ClientAttribOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(ATTRIB)),
        (TARGET_NYM, IdentifierField(optional=True)),
        (RAW, JsonField(optional=True)),
        (ENC, NonEmptyStringField(optional=True)),
        (HASH, NonEmptyStringField(optional=True)),
    )

    def _validate_message(self, msg):
        fields_n = sum(1 for f in (RAW, ENC, HASH) if f in msg)
        if fields_n == 0:
            self._raise_missed_fields(RAW, ENC, HASH)
        if fields_n > 1:
            self._raise_invalid_message(
                "only one field from {}, {}, {} is expected".format(RAW, ENC, HASH)
            )



class ClientGetAttribOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(GET_ATTR)),
        (TARGET_NYM, IdentifierField(optional=True)),
        (RAW, NonEmptyStringField()),
    )


class ClientClaimDefSubmitOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(CLAIM_DEF)),
        (REF, NonNegativeNumberField()),
        (DATA, NonEmptyStringField()),
        (SIGNATURE_TYPE, NonEmptyStringField()),
    )


class ClientClaimDefGetOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(GET_CLAIM_DEF)),
        (REF, NonNegativeNumberField()),
        (ORIGIN, NonEmptyStringField()),
        (SIGNATURE_TYPE, NonEmptyStringField()),
    )


class ClientPoolUpgradeOperation(MessageValidator):
    schema = (
        (TXN_TYPE, ConstantField(POOL_UPGRADE)),
        (ACTION, NonEmptyStringField()),  # TODO check actual value set
        (VERSION, NonEmptyStringField()),
        # TODO replace actual checks (idr, datetime)
        (SCHEDULE, MapField(NonEmptyStringField(), NonEmptyStringField(), optional=True)),
        (SHA256, NonEmptyStringField()),
        (TIMEOUT, NonNegativeNumberField(optional=True)),
        (JUSTIFICATION, NonEmptyStringField(optional=True, nullable=True)),
        (NAME, NonEmptyStringField(optional=True)),
    )


class ClientOperationField(PClientOperationField):

    _specific_operations = {
        SCHEMA: ClientSchemaOperation(),
        ATTRIB: ClientAttribOperation(),
        GET_ATTR: ClientGetAttribOperation(),
        CLAIM_DEF: ClientClaimDefSubmitOperation(),
        GET_CLAIM_DEF: ClientClaimDefGetOperation(),
        DISCLO: ClientDiscloOperation(),
        GET_NYM: ClientGetNymOperation(),
        GET_TXNS: ClientGetTxnsOperation(),
        GET_SCHEMA: ClientGetSchemaOperation(),
        POOL_UPGRADE: ClientPoolUpgradeOperation(),
    }

    operations = {**PClientOperationField.operations, **_specific_operations}


class ClientMessageValidator(PClientMessageValidator):

    # extend operation field
    schema = tuple(
        map(lambda x: (x[0], ClientOperationField()) if x[0] == OPERATION else x,
            PClientMessageValidator.schema)
    )


class LedgerIdField(PLedgerIdField):
    ledger_ids = PLedgerIdField.ledger_ids + (CONFIG_LEDGER_ID,)


# TODO do it more explicit way
# replaces some field with actual values
def patch_schemas():
    for k, v in TaggedTuples.items():
        if not issubclass(v, MessageBase):
            continue
        new_schema = []
        for name, field in v.schema:
            if isinstance(field, PLedgerIdField):
                field = LedgerIdField()
            new_schema.append((name, field))
        v.schema = tuple(new_schema)

patch_schemas()


class SafeRequest(Request, ClientMessageValidator):

    def __init__(self, **kwargs):
        self.validate(kwargs)
        super().__init__(**kwargs)
