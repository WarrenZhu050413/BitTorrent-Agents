#!/usr/bin/python

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer


class kcc_tourney(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.

        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # A list of lists, requesting all the pieces needed 
        # Symmetry breaking 
        random.shuffle(needed_pieces)
        
        peers.sort(key=lambda p: p.id) # Sorts peers by id, in ascending order [1, 2, 3, 4...]
        # request all available pieces from all peers!
        # (up to self.max_requests from each)

        # Rarest-first algorithm
        def count_peers_with_pieces(peers, needed_pieces):
            piece_counts = {piece: 0 for piece in needed_pieces}
            for peer in peers:
                for piece in peer.available_pieces:
                    if piece in piece_counts:
                        piece_counts[piece] += 1
                        
            return piece_counts

        # Sort piece count in ascending order
        piece_counts = count_peers_with_pieces(peers, needed_pieces)
        tenth_percentile = int(len(piece_counts) * 0.1)
        fortieth_percentile = int(len(piece_counts) * 0.4)
        top_ten = sorted(piece_counts.items(), key=lambda x: x[1], reverse=False)[:tenth_percentile]
        ten_to_fourty = sorted(piece_counts.items(), key=lambda x: x[1], reverse=False)[tenth_percentile: fortieth_percentile]
        fourty_after = sorted(piece_counts.items(), key=lambda x: x[1], reverse=False)[fourtieth_percentile:]
        piece_counts_sorted = ten_to_fourty + top_ten + fourty_after

        request_counts = {piece_id: 0 for piece_id in needed_pieces}
        for piece_id, count in piece_counts_sorted:
            for peer in peers: 
                num_request_per_peer = 0 
                if piece_id in peer.available_pieces and request_counts[piece_id] <= 3 and num_request_per_peer <= peer.max_requests:
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
                    request_counts[piece_id] += 1
                    num_request_per_peer += 1
        return requests 
        """
        We are employing a rarest-first algorithm, with certain alterations: 

        1. We are assuming that we want to request to at most 3 peers with the same block
        because of redundancy

        2. We are also requesting the top 10 percentile of most desired pieces after the 10th to 40th percentile, 
        because we assume that others will employ a request strategy similar to rarest-first, which means that 
        the rarest pieces will be requested first by most people, so we don't need to request those pieces first
         as they will become common. 
        """

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            alpha = 0.2
            gamma = 0.1
            r = 2

            # Esimate u_i
            random.shuffle(peers)
            downloads = history.downloads
            uploads = history.uploads

            # Randomly pick 4 elements from peers, or the mininum num of peers
            peer_four_sample = random.sample(peers, min(len(peers), 4))
            
            ### We choose to estimate the amount of capcity to require another peer to 
            ### unblock us as 25 percent of our own up_bw because the up_bw of each of 
            ### the agents are the same

            if round == 0:
                u_is = {peer.id: 0.25 * self.up_bw for peer in peers}
            else:
                for peer in peers:
                    unblockedforPastRrounds = False #shouldn't this be initialized to false?
                    other_unblock_me = False
                    i_unblock_other = False
                    for upload in uploads[-1]:
                        if upload.to_id == peer.id:
                            i_unblock_other = True
                    for download in downloads[-1]:
                        if download.from_id == peer.id:
                            other_unblock_me == True

                    for i in range(r):
                        if i < len(downloads):
                            x = False
                            for download in downloads[len(downloads) - i - 1]:
                                if download.from_id == peer.id:
                                    x = True
                            if not x:
                                unblockedforPastRrounds = False
                                break
                            
                            
                    if i_unblock_other and not other_unblock_me:
                        u_is[peer.id] = (1-gamma) * u_is[peer.id]
                    elif unblockedforPastRrounds:
                        u_is[peer.id] = (1+alpha) * u_is[peer.id]    
        

            # Estimate d_i
            downloaded_from_counter = {peer.id: 0 for peer in peers}
            for peer in peers: 
                for download in history.downloads[-1]: 
                    if download.from_id == peer.id: 
                        downloaded_from_counter[peer.id] += 1

            for peer in peers: 
                if downloaded_from_counter[peer.id] == 0: 
                    d_is[peer.id] = self.bw/4 #Directly estimate by 1/4 of my own bandwidth
                else:
                    d_is[peer.id] = downloaded_from_counter[peer.id]

            bandwidths = {peer.id: 0 for peer in peers}

            #initialize round 0 
            if round == 0: 
                chosen_requests = random.sample(requests, min(len(requests), 4))
                chosen = [request.requester_id for request in chosen_requests]
                # Evenly "split" my upload bandwidth among the one chosen requester
                bws = even_split(self.up_bw, len(chosen))
                # create actual uploads out of the list of peer ids and bandwidths
                uploads = [Upload(self.id, peer_id, bw)
                        for (peer_id, bw) in zip(chosen, bws)]
                print(uploads)
                return uploads
            else: 
                peers = sorted(peers, key = lambda p: float(d_is[p.id])/float(u_is[p.id]), reverse = True)
                m = 0
                sum = 0
                while m < len(peers) and sum <= self.up_bw:
                    sum += u_is[peers[m].id]
                    m += 1
                m -= 1
                uploads = []
                if m > 0:
                    for i in range(m):
                        uploads.append(Upload(self.id, peers[i].id, u_is[peers[i].id]))

                

                while sum < self.up_bw: 
                    available_numbers = [i for i in range(m+1, len(peers))]
                    if self.up_bw - sum < self.up_bw/4:
                        rand = random.choice(available_numbers)
                        uploads.append(Upload(self.id, peers[rand].id, self.up_bw - sum))
                        available_numbers = [i for i in available_numbers if i != rand]
                        sum = sum + self.up_bw - sum
                    elif self.up_bw - sum > self.up_bw/4:
                        rand = random.choice(available_numbers) 
                        uploads.append(Upload(self.id, peers[rand].id, self.up_bw/4))
                        available_numbers = [i for i in available_numbers if i != rand]
                        sum = sum + self.up_bw/4

                return uploads

                