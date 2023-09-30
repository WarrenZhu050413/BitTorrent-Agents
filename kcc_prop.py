import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

# from collections import defaultdict

class jjetStd(Peer):
    def post_init(self):
        print(("jjetStd post_init(): %s here!" % self.id))
        self.state = 'leecher'
        self.m = 4 # Use default of 4
        self.unblock_rounds = 2
        self.unblocked_peer = None
        self.optimistic_interval = 3
    
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """

        if self.state == 'seeder':
            return [] # No requests if we are a seeder

        requests = [] # list of Request() objects that we will return
        
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces))))) # all the pieces we need

        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        # Symmetry breaking is good...
        random.shuffle(needed_pieces)

        # Sort peers by id ascending
        peers.sort(key=lambda p: p.id) 

        # Algorithm to request pieces from peers in order of the piece rarity!

        # Track number of peers that have each piece
        piece_availability = [0] * len(self.pieces)
        for peer in peers:
            for piece in peer.available_pieces:
                piece_availability[piece] += 1
                
        # Sort needed pieces by rarity        
        sorted_needed = sorted(needed_pieces, key=lambda p: piece_availability[p])
        
        for piece in sorted_needed: # Request pieces in order of rarity
            # Select peers that have this piece
            providers = [p for p in peers if piece in p.available_pieces] 
            if providers:
                peer = random.choice(providers)
                requests.append(Request(self.id, peer.id, piece, self.pieces[piece]))

        # Check if we are done leeching and can begin seeding
        if len(needed_pieces) == 0:
            self.state = 'seeder'
        
        return requests

    '''
    A key aspect of BitTorrent is that a peer needs to decide which neighbors, if any, it will upload to. Such a peer is unblocked, while other peers are blocked. The reference client divides its upload capacity (bandwidth) equally into each of m slots (with m = 4 typical) to get the equal-split capacity. In the leecher state, the following algorithm is executed periodically, i.e., every ten seconds, and in addition, whenever an unblocked peer leaves the neighborhood or is no longer trying to download. Every time the algorithm (which we call the unblocking algorithm) is executed, we say a new round starts, and the following steps are taken by the client:
    1. Order the interested peers in decreasing order of the average download rate received from them during the last 20 seconds (breaking ties at random), also excluding any peers that have not sent any data.
    2. The m - 1 interested peers with the highest rates are unblocked via a regular unblock.
    3. In addition, every three rounds, optimistically unblock an interested peer, selected at random from those that are not already unblocked via a regular unblock, and leave this peer unblocked for the next three rounds.
    '''

    def uploads(self, requests, peers, history):

        # Extract downloads from the past rounds, up to self.unblock_rounds
        past_rounds = []
        for i, dl in enumerate(reversed(history.downloads)):
            if i >= self.unblock_rounds:
                break
            past_rounds.extend(dl)

        if self.state == 'leecher':

            # Count the blocks downloaded from each peer
            past_rounds_downloads = {}
            for dl in past_rounds:
                past_rounds_downloads[dl.from_id] = past_rounds_downloads.get(dl.from_id, 0) + dl.blocks

            # Sort peers by the amount of data they contributed in descending order
            sorted_past_dls = sorted(past_rounds_downloads.keys(), key=lambda peer_id: past_rounds_downloads[peer_id], reverse=True)
        elif self.state == 'seeder':

            # If seeding, we want to sort peers by how much we uploaded to them
            past_rounds_uploads = {}
            for ul in past_rounds:
                past_rounds_uploads[ul.to_id] = past_rounds_uploads.get(ul.to_id, 0) + ul.blocks
            
            # Sort peers by how much we uploaded to them in descending order
            sorted_past_dls = sorted(past_rounds_uploads.keys(), key=lambda peer_id: past_rounds_uploads[peer_id], reverse=True)
    

        # Filter that list for only peers who made requests from us in the current round
        requesters = {r.requester_id for r in requests}
        requesters_sorted = [peer for peer in sorted_past_dls if peer in requesters]

        # Select the top self.m peers to upload to
        to_upload = requesters_sorted[:self.m - 1]

        # Find blocked peers
        blocked_set = requesters.difference(set(to_upload))

        # Optimistic unblocking every 3 rounds
        if history.current_round() % self.optimistic_interval == 0:
            self.unblocked_peer = random.sample(list(blocked_set), 1) if blocked_set else None

        # On other rounds, still include the optimistically unblocked peer 
        if self.unblocked_peer:
            to_upload += self.unblocked_peer

        # Split bandwidth evenly among upload peers
        bws = even_split(self.up_bw, len(to_upload) if to_upload else 1)
        random.shuffle(bws)

        # Create Upload objects and return them
        return [Upload(self.id, peer_id, bw) for peer_id, bw in zip(to_upload, bws)]


