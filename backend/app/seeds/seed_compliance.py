from sqlalchemy.exc import SQLAlchemyError

from app.core.database import SESSION_LOCAL
from app.models.compliance import (
    ComplianceGroup,
    ComplianceDisclosure,
    DisclosureType,
)


def seed_compliance():
    db = SESSION_LOCAL()
    try:
        key = "dashboard_onboarding"

        group = (
            db.query(ComplianceGroup)
            .filter(ComplianceGroup.key == key)
            .first()
        )

        if not group:
            print(f"Creating group: {key}")
            group = ComplianceGroup(
                name="Dashboard Onboarding",
                key=key,
                description="Disclosures shown on dashboard entry.",
            )
            db.add(group)
            db.commit()
            db.refresh(group)
        else:
            print(f"Group {key} already exists.")

        disclosures = [
            {
                "title": "Risk Disclosure",
                "content": (
                    "Trading and investing in financial markets involves "
                    "significant risk of loss and is not suitable for every "
                    "investor. The valuation of financial instruments may "
                    "fluctuate, and clients may lose more than their "
                    "original investment."
                ),
                "type": DisclosureType.WARNING,
                "icon": "RiAlertLine",
                "color": "text-orange-500",
                "sort_order": 1,
            },
            {
                "title": "No Financial Advice",
                "content": (
                    "The information provided by FinSight is for educational "
                    "and informational purposes only and should not be "
                    "construed as investment, financial, or legal advice. "
                    "FinSight is an AI-powered insights tool, not a registered "
                    "investment advisor."
                ),
                "type": DisclosureType.INFO,
                "icon": "RiInformationLine",
                "color": "text-blue-500",
                "sort_order": 2,
            },
            {
                "title": "User Responsibility",
                "content": (
                    "You acknowledge that you are responsible for your own "
                    "investment decisions. You should consult with a "
                    "qualified professional before making any financial "
                    "decisions based on the insights provided by this "
                    "platform."
                ),
                "type": DisclosureType.SUCCESS,
                "icon": "RiShieldCheckLine",
                "color": "text-green-500",
                "sort_order": 3,
            },
        ]

        for data in disclosures:
            exists = (
                db.query(ComplianceDisclosure)
                .filter(
                    ComplianceDisclosure.group_id == group.id,
                    ComplianceDisclosure.title == data["title"],
                )
                .first()
            )

            if not exists:
                print(f"Adding disclosure: {data['title']}")
                disclosure = ComplianceDisclosure(
                    group_id=group.id,
                    title=data["title"],
                    content=data["content"],
                    disclosure_type=data["type"],
                    icon_name=data["icon"],
                    color=data["color"],
                    sort_order=data["sort_order"],
                )
                db.add(disclosure)
            else:
                print(f"Disclosure {data['title']} already exists.")

        db.commit()
        print("Seeding compliance data completed.")

    except SQLAlchemyError as exc:
        print(f"Error seeding compliance data: {exc}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_compliance()
