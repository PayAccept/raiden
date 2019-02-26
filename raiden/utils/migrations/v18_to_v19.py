import json

from web3 import Web3

from raiden.storage.sqlite import EventRecord, SQLiteStorage, StateChangeRecord

SOURCE_VERSION = 18
TARGET_VERSION = 19


def _add_blockhash_to_state_changes(storage: SQLiteStorage, web3: Web3) -> None:
    """Adds blockhash to ContractReceiveXXX and ActionInitChain state changes"""
    state_changes = storage.get_all_state_changes()
    updated_state_changes = []
    for state_change in state_changes:
        data = json.loads(state_change.data)
        affected_state_change = (
            'raiden.transfer.state_change.ContractReceive' in data['_type'] or
            'raiden.transfer.state_change.ActionInitChain' in data['_type']
        )
        if affected_state_change:
            assert 'block_hash' not in data, 'v18 state changes cant contain blockhash'
            block_number = int(data['block_number'])
            block_hash = web3.eth.getBlock(block_number)['hash']
            # use the string representation of hex bytes for the in-db string
            data['block_hash'] = block_hash.hex()

            updated_state_changes.append(StateChangeRecord(
                state_change_identifier=state_change.state_change_identifier,
                data=json.dumps(data),
            ))

    storage.update_state_changes(updated_state_changes)


def _add_blockhash_to_events(storage: SQLiteStorage, web3: Web3) -> None:
    """Adds blockhash to all ContractSendXXX events"""
    events = storage.get_all_event_records()
    updated_events = []
    for event in events:
        data = json.loads(event.data)
        if 'ContractSend' in data['_type']:
            assert 'triggered_by_block_hash' not in data, 'v18 events cant contain blockhash'
            # TODO: Get the state_change that triggered the event and if it has
            # a block number get its hash. If not fall back to latest.
            block_hash = web3.eth.getBlock('latest')['hash']
            # use the string representation of hex bytes for the in-db string
            data['triggered_by_block_hash'] = block_hash.hex()

            updated_events.append(EventRecord(
                event_identifier=event.event_identifier,
                state_change_identifier=event.state_change_identifier,
                data=json.dumps(data),
            ))

    storage.update_events(updated_events)


def upgrade_v18_to_v19(
        storage: SQLiteStorage,
        old_version: int,
        current_version: int,
        web3: Web3,
) -> int:
    if old_version == SOURCE_VERSION:
        _add_blockhash_to_state_changes(storage, web3)
        _add_blockhash_to_events(storage, web3)

    return TARGET_VERSION