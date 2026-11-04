import base64

from app.models.chain import ApprovalStep, ApproverType, StepStatus
from app.models.customer import Customer
from app.models.signature import SignatureRecord
from app.services import chain_engine
from app.services.chain_engine import ApproverSpec
from app.services.password import hash_password, verify_password

TINY_PNG_DATA_URL = (
    "data:image/png;base64,"
    + base64.b64encode(bytes.fromhex("89504e470d0a1a0a")).decode()
)


def test_customer_created_on_chain_creation(db_session, employees, document):
    chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[
            ApproverSpec(
                type=ApproverType.CUSTOMER.value,
                customer_email="client@example.com",
                customer_name="Client Person",
            )
        ],
    )
    customer = db_session.query(Customer).filter(Customer.email == "client@example.com").one()
    assert customer.password_hash is None


def test_approve_customer_step_requires_no_password_check_but_records_signature(
    db_session, employees, document
):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[
            ApproverSpec(
                type=ApproverType.CUSTOMER.value,
                customer_email="client@example.com",
                customer_name="Client Person",
            )
        ],
    )
    step = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )

    chain_engine.approve_step(db_session, step, signature_data_url=TINY_PNG_DATA_URL)

    db_session.refresh(step)
    assert step.status == StepStatus.APPROVED.value
    signature = db_session.query(SignatureRecord).filter(SignatureRecord.step_id == step.id).one()
    assert signature.image_data_url == TINY_PNG_DATA_URL


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)
