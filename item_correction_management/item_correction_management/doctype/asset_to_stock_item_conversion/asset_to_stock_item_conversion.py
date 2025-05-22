# Copyright (c) 2025, Ahmad Zubair Amini and contributors
# For license information, please see license.txt

# Asset to Stock Conversion Tool DocType
import frappe
from frappe.model.document import Document
from frappe.utils import now, get_datetime
from frappe.model.naming import make_autoname
from frappe import _


class AssettoStockItemConversion(Document):

    def on_submit(self):
        # Run all conversion functions when form is submitted
        results = []

        # 1. Convert the item from asset to stock
        item_result = update_asset_to_stock_item(self.item_name)
        results.append(f"Item Conversion: {item_result}")

        # 2. Update Purchase Receipt GL entries
        pr_result = update_receipt_gl_convert_asset_to_stock(
            self.item_name, self.asset_category, self.asset_account
        )
        results.append(f"Purchase Receipt GL Updates: {pr_result}")

        # 3. Update Purchase Invoice GL entries
        pi_result = update_invoice_gl_convert_asset_to_stock(
            self.item_name, self.asset_category, self.asset_account
        )
        results.append(f"Purchase Invoice GL Updates: {pi_result}")

        # Show summary of all operations
        frappe.msgprint("<br>".join(results))


@frappe.whitelist()
def update_asset_to_stock_item(item_name):
    try:
        # Check if already processed
        if frappe.db.exists(
            "Asset to Stock Processed",
            {
                "item_name": item_name,
            },
        ):
            return _("✅ Already processed.")

        frappe.db.set_single_value("System Settings", "allow_update_to_disabled_doc", 1)
        frappe.db.sql("SET SQL_SAFE_UPDATES = 0")

        # Update tabItem
        frappe.db.set_value(
            "Item",
            item_name,
            {
                "is_fixed_asset": 0,
                "auto_create_assets": 0,
                "asset_category": None,
                "asset_naming_series": None,
                "custom_is_service": 0,
                "is_stock_item": 1,
            },
        )

        # Update Purchase Order Item
        frappe.db.sql(
            """
            UPDATE `tabPurchase Order Item`
            SET is_fixed_asset = 0
            WHERE item_code = %s AND item_name = %s
        """,
            (item_name, item_name),
        )

        # Delete from dependent tables
        asset_names = frappe.get_all(
            "Asset", filters={"item_code": item_name}, pluck="name"
        )

        if asset_names:
            frappe.db.delete("Asset Activity", {"asset": ["in", asset_names]})
            frappe.db.delete(
                "Asset Depreciation Schedule", {"asset": ["in", asset_names]}
            )
            frappe.db.delete("Asset Movement Item", {"asset": ["in", asset_names]})
            frappe.db.delete(
                "Journal Entry Account",
                {"reference_type": "Asset", "reference_name": ["in", asset_names]},
            )

            # Delete orphan Journal Entries
            frappe.db.sql(
                """
                DELETE FROM `tabJournal Entry`
                WHERE name NOT IN (SELECT parent FROM `tabJournal Entry Account`)
            """
            )

            frappe.db.delete("Asset", {"name": ["in", asset_names]})

        # Get Purchase Receipt Items
        pri = frappe.db.sql(
            """
            SELECT pri.*, pr.posting_date, pr.posting_time, pr.owner, pr.business_category, pr.branch, 
                   pr.project, pr.docstatus, fy.name AS fiscal_year,pr.company
            FROM `tabPurchase Receipt Item` pri
            LEFT JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
            LEFT JOIN `tabFiscal Year` fy 
                ON pr.posting_date BETWEEN fy.year_start_date AND fy.year_end_date
            WHERE pri.item_code = %s AND pri.item_name = %s
              AND pr.docstatus = 1 AND pri.warehouse IS NOT NULL
              AND pri.item_code IN (SELECT name FROM `tabItem` WHERE is_stock_item = 1)
        """,
            (item_name, item_name),
            as_dict=True,
        )

        for row in pri:
            sle_doc = frappe.get_doc(
                {
                    "doctype": "Stock Ledger Entry",
                    "name": make_autoname("SLE-.########"),
                    "creation": row.posting_date,
                    "modified": row.posting_date,
                    "modified_by": row.owner,
                    "owner": row.owner,
                    "item_code": row.item_code,
                    "warehouse": row.warehouse,
                    "posting_date": row.posting_date,
                    "posting_time": row.posting_time,
                    "posting_datetime": f"{row.posting_date} {row.posting_time}",
                    "actual_qty": row.qty * row.conversion_factor,
                    "voucher_type": "Purchase Receipt",
                    "voucher_no": row.parent,
                    "voucher_detail_no": row.name,
                    "incoming_rate": row.valuation_rate,
                    "outgoing_rate": 0,
                    "company": row.company,
                    "stock_uom": row.stock_uom,
                    "batch_no": row.batch_no,
                    "serial_no": row.serial_no,
                    "is_cancelled": 0,
                    "business_category": row.business_category,
                    "branch": row.branch,
                    "project": row.project,
                    "docstatus": row.docstatus,
                    "qty_after_transaction": 0,
                    "valuation_rate": 0,
                    "stock_value": 0,
                    "stock_value_difference": 0,
                    "fiscal_year": row.fiscal_year,
                }
            )
            sle_doc.insert(ignore_permissions=True)

        # Recalculate stock valuation
        recalculate_stock_valuation(item_name)

        # Insert into tabBin
        bin_rows = frappe.db.sql(
            """
            SELECT 
                pri.item_code, pri.warehouse, pri.stock_uom,
                SUM(pri.qty * pri.conversion_factor) AS actual_qty,
                AVG(pri.valuation_rate) AS avg_valuation_rate,
                SUM(pri.qty * pri.conversion_factor * pri.valuation_rate) AS total_stock_value,
                pr.owner, pr.posting_date, pr.docstatus
            FROM `tabPurchase Receipt Item` pri
            LEFT JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
            LEFT JOIN `tabBin` bin ON pri.item_code = bin.item_code AND pri.warehouse = bin.warehouse
            WHERE pri.item_name = %s AND pri.warehouse IS NOT NULL AND pr.docstatus = 1
              AND bin.name IS NULL
            GROUP BY pri.item_code, pri.warehouse
        """,
            (item_name,),
            as_dict=True,
        )

        for b in bin_rows:
            bin_doc = frappe.get_doc(
                {
                    "doctype": "Bin",
                    "name": make_autoname("BIN-.########"),
                    "creation": b.posting_date,
                    "modified": b.posting_date,
                    "modified_by": b.owner,
                    "owner": b.owner,
                    "item_code": b.item_code,
                    "warehouse": b.warehouse,
                    "stock_uom": b.stock_uom,
                    "actual_qty": b.actual_qty,
                    "reserved_qty": 0,
                    "reserved_qty_for_production": 0,
                    "reserved_qty_for_sub_contract": 0,
                    "reserved_qty_for_production_plan": 0,
                    "reserved_stock": 0,
                    "indented_qty": 0,
                    "ordered_qty": 0,
                    "projected_qty": b.actual_qty,
                    "valuation_rate": b.avg_valuation_rate,
                    "stock_value": b.total_stock_value,
                    "docstatus": b.docstatus,
                }
            )
            bin_doc.insert(ignore_permissions=True)

        frappe.db.commit()
        return "✅ Item Operation Successfully Done"

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "update_asset_to_stock_item")
        frappe.throw(f"❌ Operation failed: {e}")

    finally:
        frappe.db.sql("SET SQL_SAFE_UPDATES = 1")


def recalculate_stock_valuation(item_code):
    warehouses = frappe.db.get_all(
        "Stock Ledger Entry",
        filters={"item_code": item_code, "docstatus": 1},
        distinct=True,
        pluck="warehouse",
    )
    for warehouse in warehouses:
        cum_qty = 0
        cum_value = 0
        sle_entries = frappe.get_all(
            "Stock Ledger Entry",
            filters={"item_code": item_code, "warehouse": warehouse, "docstatus": 1},
            fields=[
                "name",
                "actual_qty",
                "incoming_rate",
                "posting_date",
                "posting_time",
            ],
            order_by="posting_date, posting_time, name",
        )

        for entry in sle_entries:
            qty = entry.actual_qty
            rate = entry.incoming_rate
            cum_qty += qty
            cum_value += qty * rate

            valuation_rate = cum_value / cum_qty if cum_qty else 0
            stock_value = cum_qty * valuation_rate
            stock_value_diff = stock_value - (cum_value - qty * rate)

            frappe.db.set_value(
                "Stock Ledger Entry",
                entry.name,
                {
                    "qty_after_transaction": cum_qty,
                    "valuation_rate": valuation_rate,
                    "stock_value": stock_value,
                    "stock_value_difference": stock_value_diff,
                },
            )


def update_receipt_gl_convert_asset_to_stock(item_name, asset_category, asset_account):
    # Check if already processed
    if frappe.db.exists(
        "Asset to Stock Processed",
        {
            "item_name": item_name,
            "asset_category": asset_category,
            "asset_account": asset_account,
            "voucher_type": "Purchase Receipt",
        },
    ):
        return _("✅ Already processed.")

    try:
        frappe.db.begin()
        frappe.db.sql("SET SQL_SAFE_UPDATES = 0")

        # Get all purchase receipts with the item
        pr_items = frappe.db.sql(
            """
            SELECT 
                pri.parent, IFNULL(pri.amount, 0) as amount, 
                IFNULL(pri.base_amount, pri.amount) as base_amount,
                pri.item_code, pr.posting_date, pr.currency, 
                pr.owner, pr.business_category, pr.branch, pr.company,pr.currency,pr.cost_center,
                IFNULL(pr.conversion_rate, 1) as conversion_rate
            FROM `tabPurchase Receipt Item` pri
            JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
            WHERE pri.item_name = %s AND pri.asset_category = %s
            AND pr.docstatus = 1
        """,
            (item_name, asset_category),
            as_dict=True,
        )

        for row in pr_items:
            # Check if GL Entry exists
            gle_exists = frappe.db.exists(
                "GL Entry",
                {"voucher_no": row.parent, "account": "Stock In Hand - AOGC"},
            )

            # Get fiscal year
            fiscal_year = frappe.db.get_value(
                "Fiscal Year",
                {
                    "year_start_date": ["<=", row.posting_date],
                    "year_end_date": [">=", row.posting_date],
                },
                "name",
            )

            if not gle_exists:
                # Create new GL Entries
                for account, is_debit in [
                    ("Stock In Hand - AOGC", True),
                    ("Stock Received But Not Billed - AOGC", False),
                ]:
                    gl_entry = frappe.get_doc(
                        {
                            "doctype": "GL Entry",
                            "posting_date": row.posting_date,
                            "account": account,
                            "debit": row.base_amount if is_debit else 0,
                            "debit_in_account_currency": (
                                row.base_amount if is_debit else 0
                            ),
                            "debit_in_transaction_currency": (
                                row.amount if is_debit else 0
                            ),
                            "credit": 0 if is_debit else row.base_amount,
                            "credit_in_account_currency": (
                                0 if is_debit else row.base_amount
                            ),
                            "credit_in_transaction_currency": (
                                0 if is_debit else row.amount
                            ),
                            "voucher_no": row.parent,
                            "voucher_type": "Purchase Receipt",
                            "voucher_subtype": "Purchase Receipt",
                            "company": row.company,
                            "account_currency": row.currency,
                            "transaction_currency": row.currency,
                            "transaction_exchange_rate": row.conversion_rate,
                            "cost_center": row.cost_center,
                            "remarks": "Accounting Entry for Stock",
                            "branch": row.branch,
                            "against": (
                                "Stock Received But Not Billed - AOGC"
                                if is_debit
                                else "Stock In Hand - AOGC"
                            ),
                            "fiscal_year": fiscal_year,
                            "owner": row.owner,
                            "docstatus": 1,
                        }
                    )
                    gl_entry.insert(ignore_permissions=True)
            else:
                # Update existing GL entries
                frappe.db.sql(
                    """
                    UPDATE `tabGL Entry` gle
                    JOIN `tabPurchase Receipt Item` pri ON gle.voucher_no = pri.parent
                    SET 
                        gle.debit = gle.debit + IFNULL(pri.base_amount, pri.amount),
                        gle.debit_in_account_currency = gle.debit_in_account_currency + IFNULL(pri.base_amount, pri.amount),
                        gle.debit_in_transaction_currency = gle.debit_in_transaction_currency + IFNULL(pri.amount, 0)
                    WHERE 
                        gle.voucher_no = %s 
                        AND gle.account = 'Stock In Hand - AOGC' 
                        AND pri.item_code = %s
                """,
                    (row.parent, item_name),
                )

                frappe.db.sql(
                    """
                    UPDATE `tabGL Entry` gle
                    JOIN `tabPurchase Receipt Item` pri ON gle.voucher_no = pri.parent
                    SET 
                        gle.credit = gle.credit + IFNULL(pri.base_amount, pri.amount),
                        gle.credit_in_account_currency = gle.credit_in_account_currency + IFNULL(pri.base_amount, pri.amount),
                        gle.credit_in_transaction_currency = gle.credit_in_transaction_currency + IFNULL(pri.amount, 0)
                    WHERE 
                        gle.voucher_no = %s 
                        AND gle.account = 'Stock Received But Not Billed - AOGC' 
                        AND pri.item_code = %s
                """,
                    (row.parent, item_name),
                )

            # Update Asset account side
            frappe.db.sql(
                """
                UPDATE `tabGL Entry` gle
                JOIN `tabPurchase Receipt Item` pri ON gle.voucher_no = pri.parent
                SET 
                    gle.debit = gle.debit - IFNULL(pri.base_amount, pri.amount),
                    gle.debit_in_account_currency = gle.debit_in_account_currency - IFNULL(pri.base_amount, pri.amount),
                    gle.debit_in_transaction_currency = gle.debit_in_transaction_currency - IFNULL(pri.amount, 0)
                WHERE 
                    gle.account = %s
                    AND gle.against = 'Asset Received But Not Billed - AOGC'
                    AND gle.voucher_no = %s
                    AND pri.item_code = %s
            """,
                (asset_account, row.parent, item_name),
            )

            frappe.db.sql(
                """
                UPDATE `tabGL Entry` gle
                JOIN `tabPurchase Receipt Item` pri ON gle.voucher_no = pri.parent
                SET 
                    gle.credit = gle.credit - IFNULL(pri.base_amount, pri.amount),
                    gle.credit_in_account_currency = gle.credit_in_account_currency - IFNULL(pri.base_amount, pri.amount),
                    gle.credit_in_transaction_currency = gle.credit_in_transaction_currency - IFNULL(pri.amount, 0)
                WHERE 
                    gle.account = 'Asset Received But Not Billed - AOGC'
                    AND gle.against = %s
                    AND gle.voucher_no = %s
                    AND pri.item_code = %s
            """,
                (asset_account, row.parent, item_name),
            )

        # Update PR Items to remove asset reference
        frappe.db.sql(
            """
            UPDATE `tabPurchase Receipt Item`
            SET 
                is_fixed_asset = 0,
                asset_category = NULL
            WHERE 
                item_code = %s 
                AND item_name = %s
                AND asset_category = %s
        """,
            (item_name, item_name, asset_category),
        )

        # Log the processing
        frappe.get_doc(
            {
                "doctype": "Asset to Stock Processed",
                "item_name": item_name,
                "asset_category": asset_category,
                "asset_account": asset_account,
                "voucher_type": "Purchase Receipt",
            }
        ).insert(ignore_permissions=True)

        frappe.db.commit()
        return _("✅ Asset successfully converted to stock item.")

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Asset to Stock Conversion Error")
        return _("❌ Error occurred: {0}").format(str(e))

    finally:
        frappe.db.sql("SET SQL_SAFE_UPDATES = 1")


def update_invoice_gl_convert_asset_to_stock(item_name, asset_category, asset_account):
    try:
        if frappe.db.exists(
            "Asset to Stock Processed",
            {
                "item_name": item_name,
                "asset_category": asset_category,
                "asset_account": asset_account,
                "voucher_type": "Purchase Invoice",
            },
        ):
            return "✅ Already processed."

        frappe.db.sql("SET SQL_SAFE_UPDATES = 0")
        processed_items = frappe.db.sql(
            """
            SELECT 
                pini.parent as voucher_no, 
                IFNULL(pini.amount, 0) as amount, 
                IFNULL(pini.base_amount, pini.amount) as base_amount,
                pini.item_code, pin.posting_date, pin.currency, pin.company, pin.cost_center,
                pin.owner, pin.business_category, pin.branch, 
                IFNULL(pin.conversion_rate, 1) as conversion_rate,
                pin.supplier
            FROM `tabPurchase Invoice Item` pini
            JOIN `tabPurchase Invoice` pin ON pini.parent = pin.name
            WHERE pini.item_name = %s
            AND pin.docstatus = 1
        """,
            (item_name,),
            as_dict=True,
        )

        for item in processed_items:
            voucher_no = item.voucher_no

            fiscal_year = frappe.db.get_value(
                "Fiscal Year",
                {
                    "year_start_date": ["<=", item.posting_date],
                    "year_end_date": [">=", item.posting_date],
                },
                "name",
            )

            gle_exists = frappe.db.exists(
                "GL Entry",
                {
                    "voucher_no": voucher_no,
                    "account": "Stock Received But Not Billed - AOGC",
                },
            )

            if not gle_exists:
                # Create GL Entry normally (no transaction wrap)
                gl_entry = frappe.get_doc(
                    {
                        "doctype": "GL Entry",
                        "posting_date": item.posting_date,
                        "account": "Stock Received But Not Billed - AOGC",
                        "debit": item.base_amount,
                        "debit_in_account_currency": item.base_amount,
                        "debit_in_transaction_currency": item.amount,
                        "credit": 0,
                        "voucher_no": voucher_no,
                        "voucher_type": "Purchase Invoice",
                        "voucher_subtype": "Purchase Invoice",
                        "company": item.company,
                        "account_currency": item.currency,
                        "transaction_currency": item.currency,
                        "transaction_exchange_rate": item.conversion_rate,
                        "cost_center": item.cost_center,
                        "is_opening": 0,
                        "is_advance": 0,
                        "remarks": "Accounting Entry for Stock",
                        "branch": item.branch,
                        "owner": item.owner,
                        "fiscal_year": fiscal_year,
                        "against": item.supplier,
                        "docstatus": 1,
                    }
                )
                gl_entry.insert(ignore_permissions=True)

            else:
                # Update the existing GL Entries
                frappe.db.sql(
                    """
                    UPDATE `tabGL Entry` gle
                    JOIN `tabPurchase Invoice Item` pini ON gle.voucher_no = pini.parent
                    SET
                        gle.debit = gle.debit + IFNULL(pini.base_amount, pini.amount),
                        gle.debit_in_account_currency = gle.debit_in_account_currency + IFNULL(pini.base_amount, pini.amount),
                        gle.debit_in_transaction_currency = gle.debit_in_transaction_currency + IFNULL(pini.amount, 0)
                    WHERE gle.voucher_no = %s
                    AND gle.account = 'Stock Received But Not Billed - AOGC'
                    AND pini.item_code = %s
                """,
                    (voucher_no, item.item_code),
                )

            # Subtract from 'Asset Received But Not Billed'
            frappe.db.sql(
                """
                UPDATE `tabGL Entry` gle
                JOIN `tabPurchase Invoice Item` pini ON gle.voucher_no = pini.parent
                SET
                    gle.debit_in_account_currency = gle.debit_in_account_currency - IFNULL(pini.base_amount, pini.amount),
                    gle.debit = gle.debit - IFNULL(pini.base_amount, pini.amount),
                    gle.debit_in_transaction_currency = gle.debit_in_transaction_currency - IFNULL(pini.amount, 0)
                WHERE gle.account = 'Asset Received But Not Billed - AOGC'
                AND gle.voucher_no = %s
                AND pini.item_code = %s
            """,
                (voucher_no, item.item_code),
            )

            # Update 'against' field
            frappe.db.sql(
                """
                UPDATE `tabGL Entry`
                SET against = 'Asset Received But Not Billed - AOGC,Stock Received But Not Billed - AOGC'
                WHERE voucher_no = %s AND voucher_type = 'Purchase Invoice'
            """,
                (voucher_no,),
            )

        # Now insert the tracking record (no explicit commit needed)
        frappe.get_doc(
            {
                "doctype": "Asset to Stock Processed",
                "item_name": item_name,
                "asset_category": asset_category,
                "asset_account": asset_account,
                "voucher_type": "Purchase Invoice",
            }
        ).insert(ignore_permissions=True)

        return "✅ Asset successfully converted to stock item."

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Invoice GL Update Error")
        return f"❌ Error: {str(e)}"

    finally:
        frappe.db.sql("SET SQL_SAFE_UPDATES = 1")
