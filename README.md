📦 Item Correction Management for ERPNext
Author: Ahmad Zubair Amini
Repo: Item Correction Management
ERPNext Compatibility: v14–v15
License: MIT or Custom (update license.txt)

🧩 Purpose
This ERPNext module allows users to convert fixed assets (Asset Items) into Stock Items, including:

Updating item flags

Adjusting GL entries (for Purchase Receipt and Purchase Invoice)

Regenerating stock records

Ensuring clean deletion of dependent asset data

🚀 Features
Convert an Item marked as Fixed Asset to Stock Item

Clean deletion of asset-related records (Depreciation, Movement, etc.)

Rebuild Stock Ledger Entry and Bin

Adjust GL Entries for both Purchase Receipt and Purchase Invoice

Tracks each conversion in the Asset to Stock Processed doctype

📄 Doctypes
1. AssettoStockItemConversion
Main doctype to initiate the conversion. Submitting this document triggers:

update_asset_to_stock_item(item_name)

update_receipt_gl_convert_asset_to_stock(...)

update_invoice_gl_convert_asset_to_stock(...)

2. Asset to Stock Processed
Internal log to prevent re-processing the same item multiple times.

⚙️ Core Functions
Function	Location	Description
update_asset_to_stock_item(item_name)	AssettoStockItemConversion	Updates item flags, deletes asset records, inserts SLE and BIN
update_receipt_gl_convert_asset_to_stock(item_name, category, account)	same	Adjusts GL entries for Purchase Receipt
update_invoice_gl_convert_asset_to_stock(item_name, category, account)	same	Adjusts GL entries for Purchase Invoice
recalculate_stock_valuation(item_code)	same	Recomputes valuation rate and stock value for each SLE

🛠️ Developer Notes
GL accounts like "Stock In Hand - AOGC" and "Asset Received But Not Billed - AOGC" are hardcoded. Consider making them dynamic via custom settings.

Safe update mode is disabled temporarily using SET SQL_SAFE_UPDATES = 0 – ensure your MySQL settings allow it.

Avoids double entry by logging processed items into the tracking doctype.

The module does not handle serial numbers or batch splits – this can be expanded.

Multi-company logic is assumed via the company field on transactions. Test in multi-tenant setups.

🔧 Setup & Installation
bash
Copy
Edit
# Inside your bench
cd apps/
git clone https://github.com/aogc-afg/Item-Correction-Management.git item_correction_management
cd ..
bench --site yoursite install-app item_correction_management
bench migrate
📌 To-Do & Future Improvements
 Make GL account names configurable from settings

 Add test coverage

 Add UI-level validations (e.g., confirm deletion warnings)

 Add permissions and role-based access control

 Improve error handling with rollback visibility

 Add hooks to auto-validate item eligibility

🤝 Contributing
Pull requests are welcome. Please open an issue first to discuss major changes.
Ensure you test thoroughly in a development environment before proposing a change.

